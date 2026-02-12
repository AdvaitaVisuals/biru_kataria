# BIRU_BHAI Implementation Plan: Single Creator OS

## Overview
**PHILOSOPHY**: One Creator = One System. No multi-tenancy.
**GOAL**: "Autonomous Personal Content OS" that acts as a second brain.

## 1. Foundation & Infrastructure
**Goal**: Establish the "Single Brain" runtime.
- **Database**: SQLite (MVP). No `Artist` table. All data is for *The Creator*.
- **Models**:
    - `ContentAsset`: Raw video/audio.
    - `Clip`: Derived short content.
    - `Post`: distribution schedule.
    - `StrategyDecision`: Log of the "Brain's" choices.

## 2. Intelligence Layer (The Senses)
**Goal**: Turn raw media into structured data.
- **Understanding Agent**: 
  - Audio: Whisper (Speech-to-text).
  - Audio Analysis: Librosa (Beat/Energy detection).
- **Viral Cutter Agent**:
  - Logic: "Slice high-potential segments".
  - Output: 15-25 clips max (Vertical 9:16).
  - *Heavier processing logic runs in background workers.*
- **Frame Power Agent**: 
  - Extracts keyframes for thumbnails.

## 3. Strategy & Orchestration (The Brain)
**Goal**: Make decisions.
- **Strategy Brain (LangGraph)**:
  - Input: New clips, Calendar state, Past performance.
  - Output: "Post this clip tomorrow at 8 PM".
- **Memory Agent**:
  - Stores: "Comedy clips work best on Fridays".

## 4. Execution & Interface (The Hands & Mouth)
**Goal**: Action and Communication.
- **WhatsApp Control Agent**:
  - The *only* UI.
  - Commands: "Show me top clips", "Post now".
- **Auto-Posting Agent**:
  - Execute the schedule.

## 5. Technical Constraints
- **Async First**: Heavy video work (FFmpeg) never blocks the API.
- **Status Driven**: `PENDING -> PROCESSING -> READY`.
- **Local/Cloud Hybrid**: 
  - Dev: Local FFmpeg.
  - Prod: GPU Workers.
