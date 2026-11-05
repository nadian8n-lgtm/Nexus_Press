# News publishing workflow

The scheduled workflow checks the configured publisher RSS feeds hourly. It publishes only fresh stories that have matching coverage from at least two distinct publisher domains. The script uses RSS headlines and short descriptions as reporting leads; it does not copy source article text or source images. Article copy is generated as a new Arabic editorial draft, source links are shown on the article page, and the accompanying graphics are created locally as original SVG artwork.

## Required GitHub Actions secret

In the repository settings, add an Actions secret named `OPENAI_API_KEY` containing an API key authorized to call the OpenAI Chat Completions API with the configured model (`gpt-4.1-mini`). Do not put the key in this file, in source code, or in a public message. If the existing key is for another provider or is stored under a different secret name, update the workflow and API client accordingly; the workflow cannot read or infer other secret names automatically.

## Editorial safeguards and limitations

- The source list is curated in `fetch_news.py`; this is not an exhaustive search of the whole internet.
- A story is skipped if it is not recent, cannot be matched across two distinct publishers, the API is unavailable, or the originality checks fail.
- RSS does not provide complete reporting material in every case. Generated copy must not add facts not supported by the supplied source records, but automated checks cannot guarantee factual accuracy, legal compliance, or zero plagiarism. Human review is recommended for sensitive allegations, health, crime, legal matters, and developing events.
- Images are original branded SVG illustrations based on the headline, not photographs of the event. They avoid reusing publisher photographs; they should not be mistaken for documentary images.
- GitHub Actions scheduled starts can be delayed, and publication is not guaranteed to occur exactly at the start of every hour.
- The API key may incur usage charges. Set provider spending limits and monitor usage.
