        <aside class="sidebar-area">
        </aside>
    </main>
</body>
</html>
"""

    with open(filename, "w", encoding="utf-8") as output_file:
        output_file.write(html_content)


if __name__ == "__main__":
    for category_key, category in CATEGORIES_CONFIG.items():
        for index, title in enumerate(category["topics"], start=1):
            filename = f"{category_key}_{index}.html"
            generate_article_html(
                title,
                category["name"],
                category_key,
                filename,
                category["keyword"],
            )
