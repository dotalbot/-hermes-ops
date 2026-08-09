---
name: flutter-mobile-review
description: Use when Flutter UI, accessibility, navigation, lifecycle, or platform integration changes trigger.
version: 0.1.0
metadata:
  hermes:
    ownership: capability-pack
    capability_pack: flutter-mobile
    approval_state: phase2-isolated-test
---

# Flutter mobile review

Read and review only; do not edit implementation files.

Check:

1. Widget lifecycle, Riverpod state ownership, asynchronous cancellation, and mounted-context safety.
2. Navigation, focus, keyboard, terminal viewport, reconnect, and background/resume behavior.
3. Accessibility semantics, text scaling, contrast, hit targets, and non-colour state cues.
4. Android/iOS platform assumptions, permissions, secure storage, clipboard, logs, and process boundaries.
5. Tests for state transitions and user-visible failure behavior.
6. Visual evidence when the change is user-visible; code inspection alone is not visual acceptance.

Return evidence reviewed, findings ordered by severity, missing device/visual evidence, and `PASS` or `BLOCK`.
