# BIRU_BHAI Specification: Single Creator OS

## 1. Core Philosophy
**One Creator, One Brain.** No multi-tenancy. No artist IDs. All data belongs to the single user of this system.

## 2. Agent Architecture
### 2.1 Intelligence Agents
- **Understanding Agent**: Analyzes raw footage for "moments".
- **Viral Cutter Agent**: physically slices video. **Constraint**: 15-25 clips max.
- **Frame Power Agent**: extracts static imagery.
- **Caption Agent**: writes text.

### 2.2 Strategy & Learning
- **Strategy Brain**: The boss. Decides the schedule.
- **Memory Agent**: The librarian. Remembers "Action movies did well on Tuesday".
- **Analytics Agent**: The scoreboard. "Views up 20%".

### 2.3 Interface
- **WhatsApp Control Agent**: The only UI that matters.
    - "Is video ke best 5 clips?"
    - "Kal 8 baje post kar"

## 3. Data Contracts
### 3.1 Mental Model
There is **NO Artist Table**.
The database represents one brain.

### 3.2 Core Entities
- **ContentAsset**: The source material.
- **Clip**: The derived shorts.
- **Frame**: Static outputs.
- **Metric**: Performance data.
- **StrategyDecision**: Why the brain did what it did.

## 4. Orchestration Rules
- **Heavy work runs asynchronously** (Celery).
- **LangGraph** is used ONLY for decision making, NOT for processing video.
- **Status-Driven Workflow**: `PENDING -> PROCESSING -> READY -> POSTED`.

## 5. Success Metrics
- Faster content output.
- Higher engagement.
- Less manual work for the creator.
