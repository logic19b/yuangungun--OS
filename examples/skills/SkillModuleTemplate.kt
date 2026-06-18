# Skill Module Template

Template for building YuánGūnGūn OS skills.

## Quick Start

```kotlin
class MySkill : SkillModule() {
    override val name = "my_skill"
    override val version = "1.0.0"
    
    override suspend fun onLoad() {
        // Initialize resources
    }
    
    override suspend fun execute(params: Map<String, Any>): SkillResult {
        return SkillResult.Success(process(params))
    }
}
```

## Lifecycle

```
onLoad() → [idle] → execute() → [idle] → onUnload()
```

## Example: WebScraperSkill

```kotlin
class WebScraperSkill : SkillModule() {
    override val name = "web_scraper"
    override val version = "1.0.0"
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    
    override suspend fun onLoad() {
        println("WebScraperSkill initialized")
    }
    
    override suspend fun execute(params: Map<String, Any>): SkillResult {
        val url = params["url"] as? String 
            ?: return SkillResult.Error("Missing url parameter")
        
        return try {
            val html = fetch(url)
            val data = parse(html, params["selector"] as? String ?: "body")
            SkillResult.Success(data)
        } catch (e: Exception) {
            SkillResult.Error(e.message ?: "Unknown error")
        }
    }
    
    private suspend fun fetch(url: String): String {
        return withContext(Dispatchers.IO) {
            client.newCall(Request.Builder().url(url).build()).execute()
                .body?.string() ?: ""
        }
    }
    
    private fun parse(html: String, selector: String): Map<String, String> {
        // Extract structured data
        return mapOf(
            "title" to extract(html, "<title>(.*?)</title>"),
            "links" to extractAll(html, "<a href=\"(.*?)\">")
        )
    }
    
    private fun extract(html: String, regex: String): String {
        return Regex(regex, RegexOption.DOT_MATCHES_ALL)
            .find(html)?.groupValues?.get(1) ?: ""
    }
    
    private fun extractAll(html: String, regex: String): String {
        return Regex(regex, RegexOption.DOT_MATCHES_ALL)
            .findAll(html).joinToString(",") { it.groupValues[1] }
    }
    
    override suspend fun onUnload() {
        client.dispatcher.executorService.shutdown()
    }
}
```

## Security Considerations

- Validate all URLs before fetching
- Implement rate limiting
- Sanitize extracted content
- Handle timeouts gracefully

> © 2026 YuánGūnGūn & ShadowEdge Team. All rights reserved.
