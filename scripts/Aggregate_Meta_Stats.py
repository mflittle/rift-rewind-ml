#Script to aggregate the collected match data
#!/usr/bin/env python3
"""
Meta Analysis Aggregator - Custom Format
Works with flattened match data structure: {match_metadata, participants, team_stats}
"""

import boto3
import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any

def get_match_files(bucket_name: str, patch: str, queue_type: str = 'RANKED_SOLO') -> List[str]:
    """Get all match files for a specific patch"""
    s3 = boto3.client('s3')
    prefix = f'matches/{patch}/{queue_type}/'
    
    print(f"Fetching matches from {prefix}...")
    
    paginator = s3.get_paginator('list_objects_v2')
    match_files = []
    
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        if 'Contents' in page:
            match_files.extend([obj['Key'] for obj in page['Contents'] if obj['Key'].endswith('.json')])
    
    return match_files

def load_match_data(bucket_name: str, match_files: List[str]) -> List[Dict]:
    """Load all match data from S3"""
    s3 = boto3.client('s3')
    matches = []
    errors = 0
    
    for file_key in match_files:
        try:
            response = s3.get_object(Bucket=bucket_name, Key=file_key)
            match_data = json.loads(response['Body'].read())
            matches.append(match_data)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Warning: Error loading {file_key}: {e}")
            continue
    
    if errors > 5:
        print(f"  Warning: {errors} total files failed to load")
    
    return matches

def aggregate_champion_stats(matches: List[Dict]) -> Dict[str, Any]:
    """Aggregate champion statistics from custom format"""
    champion_data = defaultdict(lambda: {
        'games': 0,
        'wins': 0,
        'kills': 0,
        'deaths': 0,
        'assists': 0,
        'total_damage': 0,
        'total_cs': 0,
        'total_gold': 0,
        'total_vision_score': 0,
        'positions': defaultdict(int),
        'cs_per_min_samples': [],
        'gold_per_min_samples': [],
        'vision_per_min_samples': [],
        'damage_per_min_samples': [],
        'kda_samples': []
    })
    
    for match in matches:
        try:
            if 'participants' not in match:
                continue
            
            for participant in match['participants']:
                champion = participant.get('champion', 'Unknown')
                if champion == 'Unknown':
                    continue
                
                stats = champion_data[champion]
                stats['games'] += 1
                stats['wins'] += 1 if participant.get('win', False) else 0
                stats['kills'] += participant.get('kills', 0)
                stats['deaths'] += participant.get('deaths', 0)
                stats['assists'] += participant.get('assists', 0)
                stats['total_damage'] += participant.get('damage_dealt_champions', 0)
                stats['total_cs'] += participant.get('total_cs', 0)
                stats['total_gold'] += participant.get('gold_earned', 0)
                stats['total_vision_score'] += participant.get('vision_score', 0)
                
                # Per-minute metrics (already calculated!)
                stats['cs_per_min_samples'].append(participant.get('cs_per_min', 0))
                stats['gold_per_min_samples'].append(participant.get('gold_per_min', 0))
                stats['vision_per_min_samples'].append(participant.get('vision_per_min', 0))
                stats['damage_per_min_samples'].append(participant.get('damage_per_min', 0))
                stats['kda_samples'].append(participant.get('kda', 0))
                
                # Position tracking
                position = participant.get('position', '') or participant.get('individual_position', '')
                if position:
                    stats['positions'][position] += 1
        
        except Exception as e:
            continue
    
    # Calculate final statistics
    aggregated_stats = {}
    for champion, data in champion_data.items():
        games = data['games']
        if games == 0:
            continue
        
        aggregated_stats[champion] = {
            'games_played': games,
            'wins': data['wins'],
            'win_rate': round((data['wins'] / games) * 100, 2),
            'pick_rate': 0,  # Calculated later
            
            # Combat stats
            'avg_kills': round(data['kills'] / games, 2),
            'avg_deaths': round(data['deaths'] / games, 2),
            'avg_assists': round(data['assists'] / games, 2),
            'avg_kda': round(sum(data['kda_samples']) / len(data['kda_samples']), 2) if data['kda_samples'] else 0,
            'avg_damage': round(data['total_damage'] / games, 0),
            'avg_damage_per_min': round(sum(data['damage_per_min_samples']) / len(data['damage_per_min_samples']), 2) if data['damage_per_min_samples'] else 0,
            
            # CS & Farming
            'avg_cs': round(data['total_cs'] / games, 1),
            'avg_cs_per_min': round(sum(data['cs_per_min_samples']) / len(data['cs_per_min_samples']), 2) if data['cs_per_min_samples'] else 0,
            
            # Gold & Economy
            'avg_gold_earned': round(data['total_gold'] / games, 0),
            'avg_gold_per_min': round(sum(data['gold_per_min_samples']) / len(data['gold_per_min_samples']), 2) if data['gold_per_min_samples'] else 0,
            'gold_efficiency': round((data['total_damage'] / data['total_gold']) * 1000, 2) if data['total_gold'] > 0 else 0,
            
            # Vision & Map Control
            'avg_vision_score': round(data['total_vision_score'] / games, 1),
            'avg_vision_per_min': round(sum(data['vision_per_min_samples']) / len(data['vision_per_min_samples']), 2) if data['vision_per_min_samples'] else 0,
            
            # Position
            'primary_position': max(data['positions'], key=data['positions'].get) if data['positions'] else 'UNKNOWN',
            'position_flexibility': len([p for p, count in data['positions'].items() if count / games > 0.1])
        }
    
    # Calculate pick rates
    total_picks = sum(stats['games_played'] for stats in aggregated_stats.values())
    if total_picks > 0:
        for champion, stats in aggregated_stats.items():
            stats['pick_rate'] = round((stats['games_played'] / total_picks) * 100, 2)
    
    return aggregated_stats

def aggregate_role_meta(matches: List[Dict]) -> Dict[str, Any]:
    """Aggregate statistics by role"""
    role_data = defaultdict(lambda: {
        'games': 0,
        'wins': 0,
        'total_gold': 0,
        'total_vision': 0,
        'total_damage': 0,
        'total_cs': 0,
        'champions': defaultdict(int),
        'gold_per_min_samples': [],
        'vision_per_min_samples': []
    })
    
    for match in matches:
        try:
            if 'participants' not in match:
                continue
            
            for participant in match['participants']:
                position = participant.get('position', '') or participant.get('individual_position', '')
                if not position or position == 'Invalid':
                    continue
                
                role = role_data[position]
                role['games'] += 1
                role['wins'] += 1 if participant.get('win', False) else 0
                role['total_gold'] += participant.get('gold_earned', 0)
                role['total_vision'] += participant.get('vision_score', 0)
                role['total_damage'] += participant.get('damage_dealt_champions', 0)
                role['total_cs'] += participant.get('total_cs', 0)
                
                role['gold_per_min_samples'].append(participant.get('gold_per_min', 0))
                role['vision_per_min_samples'].append(participant.get('vision_per_min', 0))
                
                champion = participant.get('champion', 'Unknown')
                if champion != 'Unknown':
                    role['champions'][champion] += 1
        
        except Exception as e:
            continue
    
    # Calculate final role statistics
    aggregated_roles = {}
    for position, data in role_data.items():
        games = data['games']
        if games == 0:
            continue
        
        top_champions = sorted(data['champions'].items(), key=lambda x: x[1], reverse=True)[:10]
        
        aggregated_roles[position] = {
            'games_played': games,
            'win_rate': round((data['wins'] / games) * 100, 2),
            'avg_gold': round(data['total_gold'] / games, 0),
            'avg_gold_per_min': round(sum(data['gold_per_min_samples']) / len(data['gold_per_min_samples']), 2) if data['gold_per_min_samples'] else 0,
            'avg_vision_score': round(data['total_vision'] / games, 1),
            'avg_vision_per_min': round(sum(data['vision_per_min_samples']) / len(data['vision_per_min_samples']), 2) if data['vision_per_min_samples'] else 0,
            'avg_damage': round(data['total_damage'] / games, 0),
            'avg_cs': round(data['total_cs'] / games, 1),
            'top_champions': [
                {
                    'champion': champ,
                    'games': count,
                    'pick_rate_in_role': round((count / games) * 100, 2)
                }
                for champ, count in top_champions
            ]
        }
    
    return aggregated_roles

def aggregate_item_builds(matches: List[Dict]) -> Dict[str, Any]:
    """Track popular item builds by champion"""
    champion_items = defaultdict(lambda: defaultdict(int))
    
    for match in matches:
        try:
            if 'participants' not in match:
                continue
            
            for participant in match['participants']:
                champion = participant.get('champion')
                items = participant.get('items', [])
                
                if not champion or not items:
                    continue
                
                # Track item combinations (sorted for consistency)
                item_build = tuple(sorted(items))
                champion_items[champion][item_build] += 1
        
        except Exception as e:
            continue
    
    # Get top 5 builds per champion
    aggregated_items = {}
    for champion, builds in champion_items.items():
        total_games = sum(builds.values())
        if total_games == 0:
            continue
        
        top_builds = sorted(builds.items(), key=lambda x: x[1], reverse=True)[:5]
        
        aggregated_items[champion] = {
            'total_games': total_games,
            'top_builds': [
                {
                    'items': list(build),
                    'games': count,
                    'pick_rate': round((count / total_games) * 100, 2)
                }
                for build, count in top_builds
            ]
        }
    
    return aggregated_items

def aggregate_matchups(matches: List[Dict]) -> Dict[str, Any]:
    """Track head-to-head champion matchups"""
    matchup_data = defaultdict(lambda: defaultdict(lambda: {'wins': 0, 'games': 0}))
    
    for match in matches:
        try:
            if 'participants' not in match:
                continue
            
            # Group by team and position
            team_positions = {100: {}, 200: {}}
            for p in match['participants']:
                team_id = p.get('team_id')
                position = p.get('position', '') or p.get('individual_position', '')
                champion = p.get('champion')
                win = p.get('win', False)
                
                if not team_id or not position or position == 'Invalid' or not champion:
                    continue
                
                team_positions[team_id][position] = {
                    'champion': champion,
                    'win': win
                }
            
            # Track matchups per position
            for position in ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']:
                if position in team_positions[100] and position in team_positions[200]:
                    champ1 = team_positions[100][position]['champion']
                    champ2 = team_positions[200][position]['champion']
                    won1 = team_positions[100][position]['win']
                    
                    matchup_data[champ1][champ2]['games'] += 1
                    if won1:
                        matchup_data[champ1][champ2]['wins'] += 1
                    
                    matchup_data[champ2][champ1]['games'] += 1
                    if not won1:
                        matchup_data[champ2][champ1]['wins'] += 1
        
        except Exception as e:
            continue
    
    # Filter for significant matchups (at least 3 games)
    significant_matchups = {}
    for champ1, opponents in matchup_data.items():
        champ_matchups = {}
        for champ2, data in opponents.items():
            if data['games'] >= 3:
                champ_matchups[champ2] = {
                    'games': data['games'],
                    'wins': data['wins'],
                    'win_rate': round((data['wins'] / data['games']) * 100, 2)
                }
        
        if champ_matchups:
            significant_matchups[champ1] = champ_matchups
    
    return significant_matchups

def aggregate_objective_correlations(matches: List[Dict]) -> Dict[str, Any]:
    """Analyze how objectives correlate with wins"""
    objective_stats = {
        'first_blood': {'wins': 0, 'games': 0},
        'first_tower': {'wins': 0, 'games': 0},
        'first_dragon': {'wins': 0, 'games': 0},
        'first_baron': {'wins': 0, 'games': 0}
    }
    
    for match in matches:
        try:
            if 'team_stats' not in match:
                continue
            
            team_stats = match['team_stats']
            
            for team_color in ['blue', 'red']:
                if team_color not in team_stats:
                    continue
                
                team = team_stats[team_color]
                won = team.get('win', False)
                objectives = team.get('objectives', {})
                
                # Check first objectives
                for obj_name, obj_key in [
                    ('first_blood', 'first_blood'),
                    ('first_tower', 'first_tower'),
                    ('first_dragon', 'first_dragon'),
                    ('first_baron', 'first_baron')
                ]:
                    if objectives.get(obj_key):
                        objective_stats[obj_name]['games'] += 1
                        if won:
                            objective_stats[obj_name]['wins'] += 1
        
        except Exception as e:
            continue
    
    # Calculate win rates
    for objective, data in objective_stats.items():
        if data['games'] > 0:
            data['win_rate'] = round((data['wins'] / data['games']) * 100, 2)
        else:
            data['win_rate'] = 0
    
    return objective_stats

def create_meta_summary(champion_stats: Dict, role_stats: Dict, 
                       objective_stats: Dict, total_matches: int) -> Dict[str, Any]:
    """Create executive summary of meta"""
    
    # Top champions by different metrics
    top_by_winrate = sorted(
        [(champ, stats) for champ, stats in champion_stats.items() if stats['games_played'] >= 5],
        key=lambda x: x[1]['win_rate'],
        reverse=True
    )[:10]
    
    top_by_pickrate = sorted(
        champion_stats.items(),
        key=lambda x: x[1]['pick_rate'],
        reverse=True
    )[:10]
    
    top_by_gold_efficiency = sorted(
        [(champ, stats) for champ, stats in champion_stats.items() if stats['games_played'] >= 5],
        key=lambda x: x[1]['gold_efficiency'],
        reverse=True
    )[:10]
    
    top_by_vision = sorted(
        [(champ, stats) for champ, stats in champion_stats.items() if stats['games_played'] >= 5],
        key=lambda x: x[1]['avg_vision_per_min'],
        reverse=True
    )[:10]
    
    def assess_reliability(games: int) -> str:
        if games >= 300:
            return "High"
        elif games >= 150:
            return "Medium"
        elif games >= 50:
            return "Low"
        else:
            return "Very Low"
    
    summary = {
        'patch': '',
        'total_matches_analyzed': total_matches,
        'champions_with_data': len(champion_stats),
        'data_collection_date': datetime.now().isoformat(),
        'reliability_assessment': assess_reliability(total_matches),
        
        'meta_overview': {
            'top_10_by_win_rate': [
                {
                    'rank': i + 1,
                    'champion': champ,
                    'win_rate': stats['win_rate'],
                    'pick_rate': stats['pick_rate'],
                    'avg_kda': stats['avg_kda'],
                    'primary_position': stats['primary_position']
                }
                for i, (champ, stats) in enumerate(top_by_winrate)
            ],
            
            'top_10_by_pick_rate': [
                {
                    'rank': i + 1,
                    'champion': champ,
                    'pick_rate': stats['pick_rate'],
                    'win_rate': stats['win_rate'],
                    'games': stats['games_played']
                }
                for i, (champ, stats) in enumerate(top_by_pickrate)
            ],
            
            'top_10_gold_efficient': [
                {
                    'rank': i + 1,
                    'champion': champ,
                    'gold_efficiency': stats['gold_efficiency'],
                    'avg_gold_per_min': stats['avg_gold_per_min'],
                    'avg_damage': stats['avg_damage'],
                    'primary_position': stats['primary_position']
                }
                for i, (champ, stats) in enumerate(top_by_gold_efficiency)
            ],
            
            'top_10_vision_control': [
                {
                    'rank': i + 1,
                    'champion': champ,
                    'avg_vision_per_min': stats['avg_vision_per_min'],
                    'avg_vision_score': stats['avg_vision_score'],
                    'primary_position': stats['primary_position']
                }
                for i, (champ, stats) in enumerate(top_by_vision)
            ]
        },
        
        'role_economy': {
            role: {
                'avg_gold_per_min': stats['avg_gold_per_min'],
                'avg_vision_per_min': stats['avg_vision_per_min'],
                'win_rate': stats['win_rate']
            }
            for role, stats in role_stats.items()
        },
        
        'objective_importance': objective_stats,
        
        'data_quality_notes': [
            f"Sample size: {total_matches} matches - {assess_reliability(total_matches)} reliability",
            "Sample size is sufficient for reliable analysis" if total_matches >= 500 else f"Recommended minimum: 500 matches",
            f"Current data covers {len(champion_stats)} unique champions"
        ]
    }
    
    return summary

def save_to_s3(bucket_name: str, key: str, data: Dict) -> None:
    """Save aggregated data to S3"""
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )

def aggregate_match_data(bucket_name: str, patch: str, queue_type: str = 'RANKED_SOLO') -> Dict[str, Any]:
    """Main aggregation function"""
    match_files = get_match_files(bucket_name, patch, queue_type)
    print(f"Found {len(match_files)} match files for patch {patch}")
    
    if not match_files:
        print("No matches found!")
        return {}
    
    matches = load_match_data(bucket_name, match_files)
    print(f"Successfully loaded {len(matches)} matches")
    
    # Run all aggregations
    print("Aggregating champion statistics...")
    champion_stats = aggregate_champion_stats(matches)
    print(f"  ✓ Analyzed {len(champion_stats)} champions")
    
    print("Aggregating role meta...")
    role_stats = aggregate_role_meta(matches)
    print(f"  ✓ Analyzed {len(role_stats)} roles")
    
    print("Aggregating item builds...")
    item_builds = aggregate_item_builds(matches)
    
    print("Aggregating matchup data...")
    matchup_data = aggregate_matchups(matches)
    
    print("Aggregating objective correlations...")
    objective_stats = aggregate_objective_correlations(matches)
    
    print("Creating meta summary...")
    meta_summary = create_meta_summary(champion_stats, role_stats, objective_stats, len(matches))
    meta_summary['patch'] = patch
    
    # Save all aggregated data
    base_path = f'aggregated/{patch}/'
    
    outputs = {
        f'{base_path}champion_stats.json': champion_stats,
        f'{base_path}role_meta.json': role_stats,
        f'{base_path}item_builds.json': item_builds,
        f'{base_path}matchup_data.json': matchup_data,
        f'{base_path}objective_correlations.json': objective_stats,
        f'{base_path}meta_summary.json': meta_summary
    }
    
    for key, data in outputs.items():
        save_to_s3(bucket_name, key, data)
        print(f"  ✓ Saved {key}")
    
    print(f"✓ Aggregation complete!")
    
    return {
        'matches_processed': len(matches),
        'champions_analyzed': len(champion_stats),
        'aggregation_files': list(outputs.keys())
    }

if __name__ == '__main__':
    result = aggregate_match_data(
        bucket_name='rift-rewind-match-data-ml-nyc',
        patch='15.20',
        queue_type='RANKED_SOLO'
    )
    
    print(f"\n✅ Successfully processed {result['matches_processed']} matches")
    print(f"✅ Analyzed {result['champions_analyzed']} champions")
