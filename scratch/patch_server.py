with open("cutctx/proxy/server.py", "r") as f:
    content = f.read()

# Route for favicon
favicon_route = """    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        fav_path = react_assets.parent / "favicon.svg"
        if fav_path.exists():
            return FileResponse(fav_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/dashboard",
"""

content = content.replace("    @app.get(\"/dashboard\",", favicon_route)

with open("cutctx/proxy/server.py", "w") as f:
    f.write(content)

with open("cutctx/cli/proxy.py", "r") as f:
    cli_content = f.read()

cli_content = cli_content.replace(
    'URL:          {"https" if config.tls_cert else "http"}://{config.host}:{config.port}',
    'URL:          {"https" if config.tls_cert else "http"}://{config.host}:{config.port}\n  Dashboard:    {"https" if config.tls_cert else "http"}://{config.host}:{config.port}/dashboard'
)

with open("cutctx/cli/proxy.py", "w") as f:
    f.write(cli_content)
