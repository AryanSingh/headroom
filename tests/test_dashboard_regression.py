import os
import glob

def test_dashboard_assets_path_regression():
    """
    Test that the Makefile builds and copies the React dashboard assets to the correct 
    directory (cutctx/dashboard/assets) instead of nesting them in 
    cutctx/dashboard/assets/assets, which caused 404 errors on refresh.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "cutctx", "dashboard", "assets")
    
    # Assert that nested assets directory does NOT exist
    nested_assets = os.path.join(assets_dir, "assets")
    assert not os.path.exists(nested_assets), "Regression: Nested assets directory found!"
    
    # Assert that index JS and CSS are at the top level of cutctx/dashboard/assets
    js_files = glob.glob(os.path.join(assets_dir, "index-*.js"))
    css_files = glob.glob(os.path.join(assets_dir, "index-*.css"))
    
    assert len(js_files) > 0, "No built JavaScript asset found in cutctx/dashboard/assets/"
    assert len(css_files) > 0, "No built CSS asset found in cutctx/dashboard/assets/"

def test_dashboard_css_components_regression():
    """
    Test that the tab-group and tab-button components exist in the dashboard's CSS.
    Previously, they were missing, causing the UI to look like a 'gray blob'.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_file = os.path.join(base_dir, "dashboard", "src", "index.css")
    
    with open(css_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert ".tab-group" in content, "Regression: .tab-group CSS class is missing"
    assert ".tab-button" in content, "Regression: .tab-button CSS class is missing"
