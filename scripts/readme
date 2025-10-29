# League of Legends Meta Analysis Tool

AI-powered meta analysis system using AWS Bedrock Knowledge Base for natural language queries about League of Legends champion statistics, meta trends, and performance analytics.

## Overview

This project provides real-time meta analysis of high-elo (Challenger, Grandmaster, Master) League of Legends matches, enabling users to query champion statistics, item builds, vision control, and economic efficiency through natural language queries powered by Claude AI.

**Key Capabilities:**
- Query champion win rates, pick rates, and performance metrics
- Analyze vision control and gold efficiency across roles
- Compare champion matchups and meta trends
- Track objective importance and team statistics
- Multi-patch support for meta evolution tracking

---

## Data Pipeline Architecture

### Pipeline Overview

```
┌─────────────────┐
│   Riot Games    │
│      API        │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ STAGE 1: Data Collection                                 │
│ ┌─────────────────────┐    ┌────────────────────────┐   │
│ │ collect_match_ids.py│───▶│ Lambda: Match Fetcher  │   │
│ │ • Query ladders     │    │ • Fetch match details  │   │
│ │ • Get player PUUIDs │    │ • Process & validate   │   │
│ │ • Find match IDs    │    │ • Transform data       │   │
│ └─────────────────────┘    └───────────┬────────────┘   │
│                                        │                │
└────────────────────────────────────────┼────────────────┘
                                         │
                                         ▼
                            ┌────────────────────────┐
                            │ DynamoDB: Cache Table  │
                            │ • Track processed IDs  │
                            │ • Prevent duplicates   │
                            └────────────────────────┘
                                         │
                                         ▼
                            ┌────────────────────────┐
                            │   S3: Raw Match Data   │
                            │ /matches/{patch}/      │
                            │         {queue}/       │
                            └───────────┬────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────┐
│ STAGE 2: Data Aggregation                                │
│ ┌──────────────────────────────────────────────────┐    │
│ │ aggregate_meta_stats.py                          │    │
│ │ • Load raw matches from S3                       │    │
│ │ • Calculate champion statistics                  │    │
│ │ • Aggregate by role and position                 │    │
│ │ • Compute vision & gold metrics                  │    │
│ │ • Generate matchup data                          │    │
│ │ • Analyze objective correlations                 │    │
│ └──────────────────────┬───────────────────────────┘    │
│                        │                                 │
└────────────────────────┼─────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────────┐
            │ S3: Aggregated Statistics  │
            │ /aggregated/{patch}/       │
            │ • champion_stats.json      │
            │ • role_meta.json           │
            │ • item_builds.json         │
            │ • matchup_data.json        │
            │ • objective_correlations   │
            │ • meta_summary.json        │
            └────────────┬───────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STAGE 3: Knowledge Base Indexing                         │
│ ┌──────────────────────────────────────────────────┐    │
│ │ AWS Bedrock Knowledge Base                       │    │
│ │ • Titan Embeddings v2                            │    │
│ │ • Chunks: 1000 tokens, 200 overlap               │    │
│ │ • Data Sources:                                  │    │
│ │   - Game mechanics PDF                           │    │
│ │   - Aggregated match statistics                  │    │
│ └──────────────────────┬───────────────────────────┘    │
│                        │                                 │
└────────────────────────┼─────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STAGE 4: Query Interface                                 │
│ ┌──────────────────────────────────────────────────┐    │
│ │ Lambda: Bedrock Query Handler                    │    │
│ │ • Receives natural language queries              │    │
│ │ • Retrieves relevant context from KB             │    │
│ │ • Generates responses via Claude Sonnet 4.5      │    │
│ │ • Returns structured JSON responses              │    │
│ └──────────────────────┬───────────────────────────┘    │
│                        │                                 │
└────────────────────────┼─────────────────────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ End User API │
                  └──────────────┘
```

---

## Data Pipeline Stages

### Stage 1: Data Collection

**Components:**
- `collect_match_ids.py` - Python script for match ID discovery
- `match_detail_fetcher` - AWS Lambda for detailed match processing

**Process:**

1. **Ladder Query**: Script queries Riot API for top-tier players
   - Tiers: Challenger, Grandmaster, Master
   - Region: NA1 (configurable)
   - Returns ranked player list with PUUIDs

2. **Match Discovery**: For each player:
   - Fetch last 50 ranked matches using PUUID
   - Filter for RANKED_SOLO queue type
   - Collect unique match IDs
   - Skip already-cached matches (DynamoDB lookup)

3. **Match Processing**: Lambda invoked with match IDs
   - Batch size: 10 matches per invocation
   - Rate limiting: 0.5s between requests
   - Fetches full match details from Riot API
   - Validates data structure and game duration (>15 min)

4. **Data Transformation**: Lambda transforms raw API data
   - Extracts match metadata (patch, queue, duration)
   - Processes participant stats (KDA, CS, gold, vision)
   - Calculates per-minute metrics
   - Aggregates team statistics and objectives

5. **Storage**:
   - **S3**: Raw match JSON files stored by patch and queue
     - Path: `s3://bucket/matches/{patch}/{queue}/{matchId}.json`
   - **DynamoDB**: Match ID cached to prevent reprocessing
     - Table: `riot-match-cache`
     - Key: `match_id`

**Data Volume:** 517 matches collected (275 in patch 15.20, 151 in patch 15.21)

---

### Stage 2: Data Aggregation

**Component:** `aggregate_meta_stats.py`

**Process:**

1. **Data Loading**:
   - Scans S3 for all matches in specified patch
   - Loads JSON files into memory
   - Validates data structure

2. **Champion Statistics Aggregation**:
   - **Combat Metrics**: Win rate, KDA, kills, deaths, assists, damage
   - **Economic Metrics**: Gold earned, gold per minute, gold efficiency (damage per 1000 gold)
   - **Farming**: CS, CS per minute
   - **Vision Control**: Vision score, vision per minute, wards placed/killed, control wards
   - **Position Tracking**: Primary position, position flexibility

3. **Role Meta Analysis**:
   - Aggregates statistics by position (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY)
   - Calculates role-specific win rates
   - Tracks economic distribution (gold per minute by role)
   - Vision contribution by role
   - Top 10 champions per role by pick rate

4. **Item Build Tracking**:
   - Records complete item builds per champion
   - Identifies top 5 most popular builds
   - Calculates build pick rates

5. **Matchup Analysis**:
   - Tracks head-to-head champion performance
   - Records win rates in direct matchups
   - Filters for statistical significance (≥3 games)

6. **Objective Correlations**:
   - Analyzes objective impact on win probability
   - Tracks: First blood, first tower, first dragon, first baron, dragon soul
   - Calculates win rate when securing each objective

7. **Meta Summary Generation**:
   - Top 10 champions by win rate
   - Top 10 champions by pick rate
   - Top 10 champions by gold efficiency
   - Top 10 champions by vision control
   - Role economy breakdown
   - Data quality assessment

**Output Files** (saved to S3):
- `champion_stats.json` - Comprehensive champion metrics
- `role_meta.json` - Position-specific analysis
- `item_builds.json` - Popular item combinations
- `matchup_data.json` - Head-to-head win rates
- `objective_correlations.json` - Objective importance
- `meta_summary.json` - Executive summary (optimized for KB queries)

**Data Quality:** 275 matches (High reliability), 171 unique champions analyzed

---

### Stage 3: Knowledge Base Indexing

**Component:** AWS Bedrock Knowledge Base

**Configuration:**
- **Embedding Model**: Amazon Titan Embeddings v2
- **Chunking Strategy**: Fixed size (1000 tokens, 200 token overlap)
- **Data Sources**:
  1. Riot Games documentation PDF (game mechanics, champion abilities)
  2. Aggregated match statistics (S3 JSON files)

**Indexing Process:**

1. **Document Ingestion**:
   - Bedrock scans S3 bucket for JSON files
   - Parses structured data into text chunks
   - Maintains semantic relationships

2. **Embedding Generation**:
   - Creates vector embeddings for each chunk
   - Enables semantic search across statistics
   - Indexes champion names, metrics, and relationships

3. **Knowledge Graph**:
   - Links champions to statistics
   - Connects roles to meta trends
   - Associates patches with data points

**Sync Frequency:** Manual trigger after aggregation updates

---

### Stage 4: Query Interface

**Component:** Lambda function with Bedrock Runtime

**Query Flow:**

1. **Request Handling**:
   - Receives natural language query via API Gateway
   - Validates input format
   - Extracts query intent

2. **Context Retrieval**:
   - Queries Bedrock Knowledge Base
   - Retrieves top 5 relevant document chunks
   - Provides statistical context to LLM

3. **Response Generation**:
   - Uses Claude Sonnet 4.5 for natural language understanding
   - Synthesizes data from multiple sources
   - Formats response with citations
   - Includes appropriate caveats (sample size, reliability)

4. **Response Structure**:
   ```json
   {
     "success": true,
     "data": {
       "answer": "Natural language response with statistics",
       "source_documents": [...]
     }
   }
   ```

**Example Queries:**
- "What are the best support champions in patch 15.21?"
- "Which junglers have the highest gold efficiency?"
- "What's Syndra's win rate in the mid lane?"
- "Which ADCs have good vision control?"

---

## Technical Specifications

### Data Schema

**Match Metadata:**
```json
{
  "match_id": "NA1_5388628816",
  "patch": "15.20",
  "game_duration": 1847,
  "queue": "RANKED_SOLO",
  "winning_team": 100
}
```

**Participant Data:**
```json
{
  "champion": "Syndra",
  "position": "MIDDLE",
  "win": true,
  "kills": 8,
  "deaths": 3,
  "assists": 12,
  "kda": 6.67,
  "gold_earned": 14523,
  "gold_per_min": 472.4,
  "vision_score": 42,
  "vision_per_min": 1.36,
  "cs_per_min": 7.2
}
```

**Aggregated Champion Stats:**
```json
{
  "Syndra": {
    "games_played": 11,
    "win_rate": 90.91,
    "pick_rate": 1.83,
    "avg_kda": 2.77,
    "avg_gold_per_min": 425.32,
    "gold_efficiency": 85.23,
    "avg_vision_per_min": 1.24,
    "primary_position": "MIDDLE"
  }
}
```

### AWS Resources

**S3 Buckets:**
- `rift-rewind-match-data-ml-nyc`
  - `/matches/{patch}/{queue}/` - Raw match data
  - `/aggregated/{patch}/` - Processed statistics

**DynamoDB Tables:**
- `riot-match-cache`
  - Partition Key: `match_id` (String)
  - Attributes: `processed_at`, `patch`, `region`

**Lambda Functions:**
- `match_detail_fetcher` - Runtime: Python 3.12, Memory: 512MB, Timeout: 30s
- `bedrock_query_handler` - Runtime: Python 3.12, Memory: 1024MB, Timeout: 60s

**Bedrock Knowledge Base:**
- Model: Claude Sonnet 4.5
- Embeddings: Titan v2
- Vector Store: Managed by Bedrock

**Parameter Store:**
- `/rift-rewind-challenge2/riot-api-key` - Riot API key (SecureString)

---

## Data Quality & Statistics

### Current Dataset

| Metric | Value |
|--------|-------|
| Total Matches | 517 |
| Patch 15.20 Matches | 275 (High reliability) |
| Patch 15.21 Matches | 151 (Medium-High reliability) |
| Unique Champions | 171 |
| Average Rank | Challenger/Grandmaster/Master |
| Queue Type | Ranked Solo/Duo |
| Region | NA1 |

### Reliability Assessment

- **High (≥300 games)**: Patch 15.20 provides statistically significant champion data
- **Medium (150-299 games)**: Patch 15.21 provides reliable trends
- **Sample Bias**: High-elo matches may not reflect lower rank meta

### Metrics Tracked

**Per Champion:**
- Win rate, pick rate, ban rate
- KDA (kills, deaths, assists)
- Damage dealt and taken
- Gold earned and efficiency
- CS and CS per minute
- Vision score and ward metrics
- Position flexibility

**Per Role:**
- Role win rates
- Economic distribution
- Vision contribution
- Champion diversity

**Objectives:**
- First blood, tower, dragon, baron impact
- Dragon soul correlation
- Objective win rate multipliers

---

## Setup & Usage

### Prerequisites

- AWS Account with configured credentials
- Riot Games Developer API Key
- Python 3.12+
- AWS CLI configured

### Installation

```bash
# Clone repository
git clone <repository-url>
cd league-meta-analysis

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure

# Store Riot API key
aws ssm put-parameter \
    --name "/rift-rewind-challenge2/riot-api-key" \
    --value "RGAPI-your-key-here" \
    --type "SecureString"
```

### Data Collection

```bash
# Collect 150 new matches
python3 collect_match_ids.py \
    --count 150 \
    --region na1 \
    --tiers challenger grandmaster master \
    --lambda match_detail_fetcher

# Check progress
aws dynamodb scan --table-name riot-match-cache --select COUNT
```

### Data Aggregation

```bash
# Aggregate specific patch
python3 -c "
from aggregate_meta_stats import aggregate_match_data
aggregate_match_data('rift-rewind-match-data-ml-nyc', '15.21', 'RANKED_SOLO')
"

# Verify output
aws s3 ls s3://rift-rewind-match-data-ml-nyc/aggregated/15.21/
```

### Knowledge Base Sync

1. Navigate to AWS Bedrock Console
2. Select Knowledge Base
3. Click on Data Source
4. Click "Sync" button
5. Wait 5-10 minutes for indexing

### Query Examples

**Via Lambda Test:**
```json
{
  "query": "What are the top 5 mid lane champions by win rate in patch 15.21?"
}
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "answer": "Based on patch 15.21 data, the top 5 mid lane champions by win rate are:\n1. Syndra - 90.91% win rate (11.83% pick rate)\n2. Zed - 85.71% win rate (15.05% pick rate)...",
    "source_documents": [...]
  }
}
```

---

## Performance Characteristics

### Data Collection
- **Throughput**: ~50-100 matches per run (5-10 minutes)
- **Rate Limiting**: 0.5s between API calls (respects Riot API limits)
- **Lambda Cost**: ~$0.0001 per match processed
- **Storage Cost**: ~$0.01 per 1000 matches

### Aggregation
- **Processing Time**: ~30 seconds for 275 matches
- **Memory Usage**: ~200MB peak
- **Output Size**: ~150KB total aggregated files

### Query Interface
- **Response Time**: 3-8 seconds per query
- **Bedrock Cost**: ~$0.02 per query
- **Concurrency**: Up to 10 concurrent queries

---

## Limitations & Future Improvements

### Current Limitations

1. **Sample Size**: 517 matches provides good coverage but more data improves reliability
2. **Rank Coverage**: Only high-elo matches; may not reflect lower rank meta
3. **Region**: NA1 only; other regions may have different meta
4. **Update Frequency**: Manual collection; no automatic daily updates
5. **Matchup Data**: Requires 500+ matches for reliable head-to-head statistics

### Planned Improvements

1. **Automated Collection**: EventBridge schedule for daily match collection
2. **Multi-Region Support**: Expand to EUW, KR, CN regions
3. **Historical Tracking**: Store meta evolution across patches
4. **Rank Filtering**: Collect data across all ranks (Iron through Challenger)
5. **Real-time Updates**: Stream processing for live meta tracking
6. **Advanced Analytics**: Machine learning for meta prediction
7. **Web Dashboard**: User-facing Streamlit or React interface
8. **API Gateway**: Public REST API for third-party integrations

---

## License

This project is for educational purposes. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.

---

## Acknowledgments

- **Riot Games API** - Match data source
- **AWS Bedrock** - Knowledge base and LLM infrastructure
- **Anthropic Claude** - Natural language query processing
- **AWS Services** - Lambda, S3, DynamoDB, Parameter Store
