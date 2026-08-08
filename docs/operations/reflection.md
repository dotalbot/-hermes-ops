Assuming you mean the Hindsight memory system from Vectorize that you're using with Hermes: yes, 0.6.2 → 0.9.0 is a meaningful upgrade, particularly around the agent integrations rather than just bug fixes.

One important distinction: Hindsight has a core/server version and separately versioned integration plugins. The official public changelog I can verify for 0.9.0 specifically is the OpenClaw integration changelog; the GitHub core release index exposed by search is lagging behind and still shows 0.7.0 as its indexed latest. 

The biggest changes that matter

Area    0.6.2   0.9.0-era behaviour Importance

🧠 Recall defaults  Broader recall behaviour    Defaults toward observations    ⭐⭐⭐⭐⭐
🧹 Memory cleanliness   Runtime metadata could enter memories   Runtime metadata stripped   ⭐⭐⭐⭐
🔀 Session isolation    Some potential leakage/carryover    Retained docs explicitly session-scoped ⭐⭐⭐⭐⭐
🏦 Dynamic banks    Configuration inheritance issues    Banks inherit configured defaults properly  ⭐⭐⭐⭐
🤖 Per-agent banks  Identity filtering edge cases   Identity skip-filter respected  ⭐⭐⭐⭐
🛠 Tool messages    Tool messages could distort conversation slicing    Synthetic tool results excluded appropriately   ⭐⭐⭐⭐
📜 Tool replay  Anthropic-style tool blocks introduced in 0.6.2 Retained and subsequently refined   ⭐⭐⭐
🔧 Stability    Several integration/migration issues    Considerably more mature integration layer  ⭐⭐⭐⭐


The recall change is probably the most noticeable day-to-day. In 0.8.0, OpenClaw changed the default recall types so that only observations are recalled by default. That reduces irrelevant or surprising memories being injected into an agent's context. 

The memory hygiene improvements in 0.9.0 are also significant. Runtime metadata is removed from stored memory content, synthetic tool-result messages no longer interfere with how recent conversation turns are grouped, dynamic banks correctly inherit defaults, and retained documents are scoped to the current session. 

Why this matters for your Hermes architecture

This lines up particularly well with the multi-agent setup you've been building.

Hindsight's maintainers explicitly recommend a pattern where multiple agents/tools share one memory bank, rather than creating isolated memory silos for every agent. Their guidance is essentially:

┌────────────────────┐
                    │ Hindsight          │
                    │ Shared Memory Bank │
                    └─────────┬──────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
        Hermes            OpenCode          Codex
      jellyberry         jellyhome        jellybase
             │                │                │
             └────────────────┼────────────────┘
                              │
                       shared knowledge

The maintainers describe one bank that every tool reads and writes through as the canonical shared-memory pattern; separate banks are more appropriate when you actually need isolation. 

That becomes more attractive with the 0.8/0.9 changes because the integration is better at controlling what gets recalled, agent identity handling, session boundaries, and configuration inheritance.

Compared with where 0.6.2 was

0.6.2 itself was mainly a maintenance/stability release. Its headline improvements were dependency/security updates, migration fixes, and integration fixes involving Claude Code, Agent SDK, CLI and Paperclip. 

So I'd characterize the progression as:

0.6.2
   │
   │  solid maintenance/stability baseline
   ▼
0.7.x
   │
   │  integration/client maturation
   ▼
0.8.x
   │
   ├── observation-focused recall
   └── improved per-agent identity handling
   ▼
0.9.x
   │
   ├── cleaner stored memories
   ├── better conversation slicing
   ├── correct dynamic-bank defaults
   └── stronger session isolation
   ▼
Better foundation for persistent multi-agent memory

So I would upgrade rather than remain on 0.6.2.

There is one caveat for your environment: you're moving toward Hermes as the orchestrator with several subordinate agents. I wouldn't blindly use one enormous memory bank for everything. I'd probably design your Hindsight banking something like shared personal/operational memory + project-specific banks + deliberately isolated agent/task banks, rather than either extreme of "one bank for absolutely everything" or "one bank per agent."

[Hindsight GitHub repository](https://github.com/vectorize-io/hindsight?utm_source=chatgpt.com) · [Hindsight integration changelog](https://hindsight.vectorize.io/changelog/integrations/openclaw?utm_source=chatgpt.com)

If you want, I can next look specifically at Hindsight 0.9.0 + Hermes and map out what you should change in your current Jellyberry/Jellybase multi-agent configuration. 
