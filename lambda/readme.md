# Lambda Functions

This directory contains three AWS Lambda functions that power the League of Legends Analytics Platform.

## Functions Overview

### 1. chat-agent-handler
**Purpose:** AI chat agent powered by AWS Bedrock  
**Trigger:** WebSocket API Gateway  
**Runtime:** Python 3.13  
**Memory:** 512 MB  
**Timeout:** 300 seconds

The main conversational AI that answers League of Legends questions using a Knowledge Base of high-elo match data.

### 2. riot-api-function
**Purpose:** Summoner stats and champion mastery lookup  
**Trigger:** Lambda Function URL (public HTTPS endpoint)  
**Runtime:** Python 3.13  
**Memory:** 128 MB  
**Timeout:** 30 seconds

Fetches live summoner data and top 5 champion mastery stats from the Riot Games API.

### 3. match_detail_fetcher
**Purpose:** Processes raw match data for Knowledge Base  
**Trigger:** Direct invocation (from data collection scripts)  
**Runtime:** Python 3.12  
**Memory:** 512 MB  
**Timeout:** 120 seconds

Fetches detailed match information from Riot API, transforms it, and stores in S3 for aggregation.

---

## Function Details

### chat-agent-handler

**What it does:**
- Receives natural language questions via WebSocket
- Uses AWS Bedrock Knowledge Base to retrieve relevant match data
- Generates responses using Claude 3.5 Haiku
- Maintains conversation history within the session
- Returns structured responses with champion builds, strategies, and statistics

**Architecture:**
```
WebSocket API Gateway
    ↓
chat-agent-handler (Lambda)
    ↓
    ├─→ AWS Bedrock Knowledge Base (League match data)
    └─→ Claude 3.5 Haiku (response generation)
```

**Environment Variables:**
- `KNOWLEDGE_BASE_ID` - AWS Bedrock Knowledge Base ID
- `MODEL_ID` - Claude model identifier (us.anthropic.claude-3-5-haiku-20241022-v1:0)
- `REGION` - AWS region (us-east-1)

**Input Format:**
```json
{
  "messages": [
    {"role": "user", "content": "What are the best items for Jinx?"}
  ]
}
```

**Output Format:**
```json
{
  "type": "chunk",
  "content": "Based on high-elo match data, the best items for Jinx are..."
}
```

**Key Optimizations:**
- Uses `retrieve()` instead of `retrieve_and_generate()` for 3x faster responses
- Switched from Sonnet to Haiku for speed (12s → 3-4s synthesis)
- Progressive thinking messages for better UX during 15-20s queries

**Dependencies:**
- `strands` - AI agent framework
- `boto3` - AWS SDK

---

### riot-api-function

**What it does:**
- Accepts a Riot ID (e.g., "Doublelift#NA1")
- Fetches summoner account details from Riot Games API
- Retrieves top 5 champion mastery data
- Returns formatted JSON with profile info and champion stats

**Architecture:**
```
Website (Frontend)
    ↓ HTTPS POST
Lambda Function URL
    ↓
riot-api-function
    ↓
Riot Games API (account-v1, summoner-v4, champion-mastery-v4)
```

**Environment Variables:**
- `RIOT_API_KEY_PARAM` - Parameter Store path for Riot API key (default: `/rift-rewind-challenge2/riot-api-key`)

**Input Format:**
```json
{
  "riotId": "Doublelift#NA1",
  "region": "americas",
  "platform": "na1"
}
```

**Output Format:**
```json
{
  "summoner": {
    "gameName": "Doublelift",
    "tagLine": "NA1",
    "level": 31,
    "profileIconId": 4568
  },
  "topChampions": [
    {
      "championName": "Vayne",
      "championTitle": "the Night Hunter",
      "championImage": "Vayne.png",
      "championLevel": 15,
      "championPoints": 181371
    }
  ]
}
```

**Rate Limiting:**
- Riot API has rate limits (20 requests/second, 100 requests/2 minutes)
- Function includes basic error handling for rate limit responses
- Consider implementing caching for frequently-looked-up summoners

**Region Mapping:**
```python
{
  'na1': 'americas',
  'br1': 'americas',
  'la1': 'americas',
  'la2': 'americas',
  'euw1': 'europe',
  'eune1': 'europe',
  'tr1': 'europe',
  'ru': 'europe',
  'kr': 'asia',
  'jp1': 'asia',
  'oc1': 'sea'
}
```

**Dependencies:**
- `boto3` - AWS SDK (for Parameter Store)
- `requests` - HTTP library

---

### match_detail_fetcher

**What it does:**
- Accepts a batch of League of Legends match IDs
- Fetches full match details from Riot API
- Transforms raw data into structured format
- Stores matches in S3 (organized by patch and queue type)
- Caches processed match IDs in DynamoDB to prevent duplicates

**Architecture:**
```
Data Collection Script
    ↓ Invoke with match IDs
match_detail_fetcher (Lambda)
    ↓
    ├─→ Riot Games API (match-v5)
    ├─→ S3 (store match JSON)
    └─→ DynamoDB (cache match ID)
```

**Environment Variables:**
- `RIOT_API_KEY_PARAM` - Parameter Store path for Riot API key
- `S3_BUCKET` - Target S3 bucket (rift-rewind-match-data-ml-nyc)
- `DYNAMODB_TABLE` - Cache table name (riot-match-cache)

**Input Format:**
```json
{
  "match_ids": ["NA1_5388628816", "NA1_5388629123"],
  "region": "americas"
}
```

**S3 Storage Structure:**
```
s3://bucket/matches/{patch}/{queue}/{matchId}.json

Example:
s3://rift-rewind-match-data-ml-nyc/matches/15.21/RANKED_SOLO/NA1_5388628816.json
```

**Processed Match Schema:**
```json
{
  "match_id": "NA1_5388628816",
  "patch": "15.21",
  "game_duration": 1847,
  "queue": "RANKED_SOLO",
  "winning_team": 100,
  "participants": [
    {
      "champion": "Syndra",
      "position": "MIDDLE",
      "win": true,
      "kills": 8,
      "deaths": 3,
      "assists": 12,
      "gold_earned": 14523,
      "vision_score": 42,
      "cs_per_min": 7.2
    }
  ]
}
```

**DynamoDB Cache:**
- Prevents reprocessing of matches
- Tracks when each match was processed
- Stores patch version and region

**Dependencies:**
- `boto3` - AWS SDK

---

## Deployment

### Prerequisites
- AWS CLI configured with appropriate credentials
- Python 3.12+ installed locally
- IAM permissions for Lambda, S3, DynamoDB, Parameter Store, Bedrock

### Setup Riot API Key

```bash
# Store your Riot API key in Parameter Store
aws ssm put-parameter \
    --name "/rift-rewind-challenge2/riot-api-key" \
    --value "RGAPI-your-api-key-here" \
    --type "SecureString" \
    --overwrite
```

### Deploy chat-agent-handler

```bash
# Create deployment package
cd chat-agent-handler/
pip install -r requirements.txt -t .
zip -r function.zip .

# Upload to Lambda
aws lambda update-function-code \
    --function-name chat-agent-handler \
    --zip-file fileb://function.zip

# Set environment variables
aws lambda update-function-configuration \
    --function-name chat-agent-handler \
    --environment Variables="{
        KNOWLEDGE_BASE_ID=YOUR_KB_ID,
        MODEL_ID=us.anthropic.claude-3-5-haiku-20241022-v1:0,
        REGION=us-east-1
    }"
```

### Deploy riot-api-function

```bash
# Create deployment package
cd riot-api-function/
pip install -r requirements.txt -t .
zip -r function.zip .

# Upload to Lambda
aws lambda update-function-code \
    --function-name riot-api-function \
    --zip-file fileb://function.zip

# Create Function URL (if not exists)
aws lambda create-function-url-config \
    --function-name riot-api-function \
    --auth-type NONE \
    --cors '{
        "AllowOrigins": ["*"],
        "AllowMethods": ["POST"],
        "AllowHeaders": ["content-type"],
        "MaxAge": 3600
    }'
```

### Deploy match_detail_fetcher

```bash
# Create deployment package
cd match_detail_fetcher/
pip install -r requirements.txt -t .
zip -r function.zip .

# Upload to Lambda
aws lambda update-function-code \
    --function-name match_detail_fetcher \
    --zip-file fileb://function.zip

# Set environment variables
aws lambda update-function-configuration \
    --function-name match_detail_fetcher \
    --environment Variables="{
        S3_BUCKET=rift-rewind-match-data-ml-nyc,
        DYNAMODB_TABLE=riot-match-cache,
        RIOT_API_KEY_PARAM=/rift-rewind-challenge2/riot-api-key
    }"
```

---

## IAM Permissions

### chat-agent-handler Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:Retrieve",
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "execute-api:ManageConnections"
      ],
      "Resource": "arn:aws:execute-api:*:*:*/@connections/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### riot-api-function Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/rift-rewind-challenge2/riot-api-key"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### match_detail_fetcher Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::rift-rewind-match-data-ml-nyc/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/riot-match-cache"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/rift-rewind-challenge2/riot-api-key"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Testing

### Test chat-agent-handler

```bash
# Via AWS CLI (requires WebSocket client)
# Or test through the website at:
# https://main.d34u5e3l1s0uex.amplifyapp.com/

# Ask a question and verify response time (~17 seconds)
```

### Test riot-api-function

```bash
# Get the Function URL
FUNCTION_URL=$(aws lambda get-function-url-config \
    --function-name riot-api-function \
    --query 'FunctionUrl' \
    --output text)

# Test lookup
curl -X POST $FUNCTION_URL \
    -H "Content-Type: application/json" \
    -d '{
        "riotId": "Doublelift#NA1",
        "region": "americas",
        "platform": "na1"
    }'
```

### Test match_detail_fetcher

```bash
# Test with a single match ID
aws lambda invoke \
    --function-name match_detail_fetcher \
    --payload '{
        "match_ids": ["NA1_5388628816"],
        "region": "americas"
    }' \
    response.json

# Check output
cat response.json
```

---

## Monitoring

### CloudWatch Logs

Each function logs to CloudWatch Logs:
- `/aws/lambda/chat-agent-handler`
- `/aws/lambda/riot-api-function`
- `/aws/lambda/match_detail_fetcher`

### Key Metrics to Monitor

**chat-agent-handler:**
- Duration (should be ~17 seconds)
- Errors (rate limit or Bedrock throttling)
- Concurrent executions

**riot-api-function:**
- Duration (should be <5 seconds)
- Riot API rate limit errors (429 responses)
- Invalid summoner name errors

**match_detail_fetcher:**
- Duration per match (~2-3 seconds)
- S3 write errors
- DynamoDB cache hits

---

## Troubleshooting

### chat-agent-handler slow (>30 seconds)
- Check Bedrock Knowledge Base chunk size (should be 400-500 tokens, not 1000)
- Verify using Haiku model, not Sonnet
- Review CloudWatch logs for tool call times

### riot-api-function returning errors
- Verify Riot API key is valid and not expired (daily dev keys expire)
- Check Parameter Store has correct key
- Verify summoner name format: "GameName#TAG" (case sensitive)

### match_detail_fetcher timeout
- Reduce batch size (fewer match IDs per invocation)
- Check Riot API rate limits
- Verify S3 and DynamoDB permissions

### CORS errors on riot-api-function
- Ensure Function URL has CORS configured:
  ```bash
  aws lambda get-function-url-config --function-name riot-api-function
  ```
- AllowOrigins should include your Amplify domain

---

## Performance Optimization History

**chat-agent-handler improvements:**
1. Initial: 114 seconds (using retrieve_and_generate)
2. After switching to retrieve(): 44 seconds
3. After switching to Haiku: 17 seconds (current)

**Total improvement: 85% faster** ⚡

---

## Cost Estimates

**Per 1000 invocations:**
- chat-agent-handler: ~$0.50 (Bedrock + Lambda)
- riot-api-function: ~$0.01 (Lambda only)
- match_detail_fetcher: ~$0.05 (Lambda + S3 + DynamoDB)

**Note:** Riot API calls are free (within rate limits), Bedrock charges per token.

---

## License

This project is for educational purposes. League of Legends and Riot Games are trademarks of Riot Games, Inc.
