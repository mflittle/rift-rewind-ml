#Collect Match IDs using the Riot API
#!/usr/bin/env python3
"""
Simple Match ID Collector - Run Locally
For MVP: Get 500 match IDs quickly without deploying a second Lambda

Usage:
    python collect_match_ids.py --count 100
    python collect_match_ids.py --count 200 --region na1
"""

import boto3
import requests
import json
import time
import argparse
from datetime import datetime

def get_api_key():
    """Get Riot API key from AWS Parameter Store"""
    ssm = boto3.client('ssm')
    try:
        parameter = ssm.get_parameter(
            Name='/rift-rewind-challenge2/riot-api-key',
            WithDecryption=True
        )
        return parameter['Parameter']['Value']
    except Exception as e:
        print(f"Error getting API key from Parameter Store: {e}")
        print("\nAlternatively, you can hardcode your API key:")
        print("  API_KEY = 'RGAPI-your-key-here'")
        exit(1)

def get_routing_value(region):
    """Map platform region to routing value"""
    routing_map = {
        'na1': 'americas',
        'br1': 'americas',
        'la1': 'americas',
        'la2': 'americas',
        'euw1': 'europe',
        'eun1': 'europe',
        'tr1': 'europe',
        'ru': 'europe',
        'kr': 'asia',
        'jp1': 'asia',
        'oc1': 'sea',
    }
    return routing_map.get(region, 'americas')

def get_high_elo_players(region, api_key, tier='challenger', max_players=30):
    """Get list of high-elo players"""
    headers = {"X-Riot-Token": api_key}
    
    # Get ladder
    ladder_url = f"https://{region}.api.riotgames.com/lol/league/v4/{tier}leagues/by-queue/RANKED_SOLO_5x5"
    
    print(f"Fetching {tier} ladder from {region}...")
    response = requests.get(ladder_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching ladder: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        return []
    
    data = response.json()
    entries = data.get('entries', [])[:max_players]
    print(f"Found {len(entries)} {tier} players")
    
    return entries

def get_player_puuid(summoner_id, region, api_key):
    """Get PUUID from summoner ID"""
    headers = {"X-Riot-Token": api_key}
    summoner_url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    
    response = requests.get(summoner_url, headers=headers)
    if response.status_code != 200:
        return None
    
    return response.json()['puuid']

def get_player_matches(puuid, routing_value, api_key, count=50):
    """Get recent match IDs for a player"""
    headers = {"X-Riot-Token": api_key}
    
    # Get only ranked solo/duo matches (queue 420)
    match_url = f"https://{routing_value}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&count={count}"
    
    response = requests.get(match_url, headers=headers)
    if response.status_code != 200:
        return []
    
    return response.json()

def check_match_cached(match_id):
    """Check if match already exists in DynamoDB cache"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('riot-match-cache')
        response = table.get_item(Key={'match_id': match_id})
        return 'Item' in response
    except Exception as e:
        # If table doesn't exist, assume not cached
        return False

def collect_match_ids(region='na1', target_count=100, tiers=['challenger', 'grandmaster']):
    """
    Main collection function
    
    Args:
        region: Riot region (na1, euw1, kr, etc.)
        target_count: Target number of unique match IDs
        tiers: List of rank tiers to collect from
    """
    api_key = get_api_key()
    routing_value = get_routing_value(region)
    
    all_match_ids = set()
    new_match_ids = []  # Matches not in cache
    players_processed = 0
    
    print(f"\n{'='*60}")
    print(f"Match ID Collection")
    print(f"Region: {region}")
    print(f"Target: {target_count} unique matches")
    print(f"Tiers: {', '.join(tiers)}")
    print(f"{'='*60}\n")
    
    for tier in tiers:
        #if len(new_match_ids) >= target_count:
            #break
        
        # Get high-elo players
        players = get_high_elo_players(region, api_key, tier, max_players=50)
        
        for idx, entry in enumerate(players):
            # Process at least 30 players from each tier before checking count
            if idx >= 30 and len(new_match_ids) >= target_count:
                break
                    
        # Get PUUID directly from entry (no separate API call needed!)
        puuid = entry.get('puuid')

        if not puuid:
            print(f"  Skipping entry - no PUUID found")
            continue

        try:
            # Get match list
            match_ids = get_player_matches(puuid, routing_value, api_key, count=50)
            
            # Add to our set and check cache
            for match_id in match_ids:
                all_match_ids.add(match_id)
                
                if not check_match_cached(match_id):
                    new_match_ids.append(match_id)
            
            players_processed += 1
            print(f"[{players_processed}] Player {players_processed}: +{len(match_ids)} matches | "
                f"Total unique: {len(all_match_ids)} | New: {len(new_match_ids)}")
            
            # Rate limiting - don't hammer the API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error processing player {players_processed + 1}: {e}")
            continue
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save ALL match IDs (including cached)
    all_filename = f'match_ids_all_{timestamp}.json'
    with open(all_filename, 'w') as f:
        json.dump(list(all_match_ids), f, indent=2)
    
    # Save NEW match IDs (not cached)
    new_filename = f'match_ids_new_{timestamp}.json'
    with open(new_filename, 'w') as f:
        json.dump(new_match_ids, f, indent=2)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"COLLECTION COMPLETE")
    print(f"{'='*60}")
    print(f"Players processed: {players_processed}")
    print(f"Total unique matches: {len(all_match_ids)}")
    print(f"New matches (not cached): {len(new_match_ids)}")
    print(f"\nFiles saved:")
    print(f"  All matches: {all_filename}")
    print(f"  New matches: {new_filename}")
    print(f"{'='*60}\n")
    
    return new_match_ids

def invoke_lambda_with_matches(match_ids, lambda_name, region='na1', batch_size=10):
    """
    Invoke your Lambda function with collected match IDs
    
    Args:
        match_ids: List of match IDs to process
        lambda_name: Name of your Lambda function
        region: Riot region
        batch_size: Matches per invocation
    """
    if not match_ids:
        print("No new matches to process!")
        return
    
    lambda_client = boto3.client('lambda')
    
    print(f"\n{'='*60}")
    print(f"INVOKING LAMBDA: {lambda_name}")
    print(f"{'='*60}")
    print(f"Total matches: {len(match_ids)}")
    print(f"Batch size: {batch_size}")
    print(f"Invocations: {len(match_ids) // batch_size + 1}")
    print(f"{'='*60}\n")
    
    invocations = 0
    processed = 0
    
    for i in range(0, len(match_ids), batch_size):
        batch = match_ids[i:i+batch_size]
        
        payload = {
            "matchIds": batch,
            "region": region
        }
        
        try:
            response = lambda_client.invoke(
                FunctionName=lambda_name,
                InvocationType='Event',  # Async
                Payload=json.dumps(payload)
            )
            
            invocations += 1
            processed += len(batch)
            
            print(f"[{invocations}] Invoked with {len(batch)} matches | Total: {processed}/{len(match_ids)}")
            
            # Small delay to avoid overwhelming Lambda
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error invoking Lambda: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"LAMBDA INVOCATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total invocations: {invocations}")
    print(f"Matches queued: {processed}")
    print(f"\nCheck CloudWatch logs for processing status")
    print(f"Check S3 for match data: s3://rift-rewind-match-data-ml-nyc/matches/")
    print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description='Collect League of Legends match IDs for meta analysis')
    parser.add_argument('--count', type=int, default=100, help='Target number of matches (default: 100)')
    parser.add_argument('--region', default='na1', help='Riot region (default: na1)')
    parser.add_argument('--tiers', nargs='+', default=['challenger', 'grandmaster'], 
                        help='Rank tiers to collect from (default: challenger grandmaster)')
    parser.add_argument('--lambda', dest='lambda_name', help='Lambda function name (auto-invoke after collection)')
    parser.add_argument('--batch-size', type=int, default=10, help='Matches per Lambda invocation (default: 10)')
    
    args = parser.parse_args()
    
    # Collect match IDs
    new_matches = collect_match_ids(
        region=args.region,
        target_count=args.count,
        tiers=args.tiers
    )
    
    # Optionally invoke Lambda
    if args.lambda_name and new_matches:
        invoke_lambda_with_matches(
            match_ids=new_matches,
            lambda_name=args.lambda_name,
            region=args.region,
            batch_size=args.batch_size
        )
    elif args.lambda_name:
        print("No new matches to process!")
    else:
        print("\nTo invoke Lambda with these matches, run:")
        print(f"  python collect_match_ids.py --lambda YOUR_LAMBDA_NAME")

if __name__ == '__main__':
    main()
