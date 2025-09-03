"""Documentation configuration for EasyGo Education."""

source_link = "https://github.com/easygo-education/easygo_education"
docs_base_url = "https://easygo-education.github.io/easygo_education"
headline = "Comprehensive educational institution management system"
sub_heading = "Built for Moroccan schools with bilingual support"

def get_context(context):
    """Add context for documentation."""
    context.brand_name = "EasyGo Education"
    context.top_bar_items = [
        {"label": "User Guide", "url": docs_base_url + "/user"},
        {"label": "API", "url": docs_base_url + "/api"},
        {"label": "GitHub", "url": source_link},
    ]
