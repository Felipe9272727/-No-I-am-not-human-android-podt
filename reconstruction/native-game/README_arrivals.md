# Character arrival scheduler

`VisitorScheduler` models one `GenerateCharacterDingDongsForDay` batch. Each staged event must have exactly one configured day, and all events in the batch must share it. Stable sorting preserves insertion order for equal order values. In the sorted order, each event receives every earlier visit name as an additional prerequisite; this intentionally does not create cross-day dependencies.

At update, the scheduler performs the native fake preflight with `last_daytime_change - 1.0f`, which moves the warning threshold one second earlier. A successful fake check is non-consuming. It then performs the real check with the unadjusted time and invokes arrival subscribers in registration order. Completion is still external: a triggered event name enters the prerequisite set only when the host marks that event completed.

Evidence basis: the recovered original methods are `GenerateCharacterDingDongsForDay`, `GenerateDingDongEventsOrder`, and `AGameEvent.CheckConditions`. The single-day guard reflects that native ordering is requested for an individual day; it prevents accidental prerequisite chaining across day batches. Visit names, characters, delay randomization, and roster construction must come from recovered source data and are not fabricated by this scheduler.
