# ORVEXA 1.1.0 Changelog

## Fixed

- Updating the baseline heart rate no longer adds a fabricated measurement. The profile is saved in one transaction; existing measurements remain unchanged.
- Analysis is tied to the actual metric context. Stale, cancelled, or post-close responses are ignored.
- Completing a background request no longer clears settings or next-message drafts. Changing the chart period preserves the current page and scroll position.
- Empty charts no longer draw a fabricated baseline point. Distances between points reflect measurement timestamps.
- Incomplete and refused OpenAI responses, Ollama errors, invalid JSON, and oversized responses are handled explicitly. Local Ollama requests bypass external proxies and do not follow redirects.
- Chat receives a bounded context of recent messages.
- The Start button is disabled when no exercises are available. An empty AI plan is never replaced with a sample plan.
- The timer stops at exercise boundaries and when the dialog closes. Completing a workout twice does not inflate the completed count. Partial workouts can be saved or discarded.
- Long instructions are scrollable; the 16-hour sleep limit prevents extra minutes. Sleep above 9 hours is no longer marked as within range.
- CSV/JSON output matches the selected file extension. Exports are written to a temporary file and atomically replaced; a failed write preserves the previous report.
- SQLite errors do not replace the interface state with unsaved measurements. A corrupted analysis cache does not prevent startup.
- The launcher restores missing pip after an interrupted virtual-environment setup.

## Performance

- The latest 200 measurements are loaded at startup. History is paginated, statistics are calculated with SQL, and full export remains available.
- Added SQLite indexes, time-series caching, and image/icon caching. Switching chart metrics refreshes the chart card.
- Chart rendering is capped at 600 points while retaining first/last values and local minima/maxima. Sparklines are capped at 80 points.
- Closed dialogs and replaced widgets are released.
- The decorative mission card is hidden in compact windows while navigation and fields remain accessible.

## Verification Notes

The original 44 checks were run on Linux/Python 3.12/Qt 6.8.3, with GUI tests using Qt offscreen. Windows execution was not available in that environment. Live external model use without a key or installed Ollama was not tested; the network protocol and full workflow were checked with a local test server.

In a like-for-like local benchmark with 10,000 measurements, startup decreased from 488 ms to 157 ms, and switching among four charts decreased from 1,470 ms to 36 ms. These measurements describe the test environment; performance may vary on other computers.
