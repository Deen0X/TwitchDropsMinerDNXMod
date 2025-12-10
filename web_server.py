
import asyncio
import logging
import json
import os
from aiohttp import web
from typing import TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from twitch import Twitch

logger = logging.getLogger("TwitchDrops.web")

class WebServer:
    def __init__(self, twitch: "Twitch", port: int = 5801):
        self._twitch = twitch
        self._port = port
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self.setup_routes()

    def setup_routes(self):
        self._app.router.add_get('/', self.handle_index)
        self._app.router.add_get('/api/status', self.handle_status)
        self._app.router.add_get('/api/inventory', self.handle_inventory)
        self._app.router.add_get('/icon.png', self.handle_icon)
        # Serve static files if needed, but for now single page + icon is enough
        self._app.router.add_static('/static', path=Path(__file__).parent / 'web', append_version=True)

    async def start(self):
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, '0.0.0.0', self._port)
        await self._site.start()
        logger.info(f"Web server started on http://localhost:{self._port}")

    async def stop(self):
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("Web server stopped")

    async def handle_index(self, request):
        index_path = Path(__file__).parent / 'web' / 'index.html'
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(text="Web Interface Error: index.html not found", status=404)

    async def handle_icon(self, request):
        icon_path = Path(__file__).parent / 'web' / 'icon.png'
        if icon_path.exists():
            return web.FileResponse(icon_path)
        return web.Response(status=404)

    async def handle_status(self, request):
        # Gather data from twitch instance
        t = self._twitch
        
        # Current progress
        drop = t.gui.progress._drop
        campaign_vars = t.gui.progress._vars["campaign"]
        
        status_data = {
            "state": t._state.name if t._state else "UNKNOWN",
            "active_campaign": campaign_vars["name"].get(),
            "active_game": campaign_vars["game"].get(),
            "campaign_progress": campaign_vars["percentage"].get(),
            "campaign_remaining": campaign_vars["remaining"].get(),
            "drop_rewards": t.gui.progress._vars["drop"]["rewards"].get(),
            "drop_progress_percent": t.gui.progress._vars["drop"]["percentage"].get(),
            "drop_remaining": t.gui.progress._vars["drop"]["remaining"].get(),
            "logged_in": t._auth_state._logged_in.is_set(),
            "user_id": getattr(t._auth_state, "user_id", None),
        }
        return web.json_response(status_data)

    async def handle_inventory(self, request):
        t = self._twitch
        inventory_data = []
        for campaign in t.inventory:
            drops_data = []
            for drop in campaign.drops:
                drops_data.append({
                    "id": drop.id,
                    "name": drop.rewards_text(),
                    "progress": drop.progress,
                    "is_claimed": drop.is_claimed,
                    "can_claim": drop.can_claim,
                    "image_url": drop.benefits[0].image_url if drop.benefits else None
                })
            
            inventory_data.append({
                "id": campaign.id,
                "game": campaign.game.name,
                "name": campaign.name,
                "status": "Active" if campaign.active else ("Upcoming" if campaign.upcoming else "Expired"),
                "progress": campaign.progress,
                "drops": drops_data,
                "start_at": str(campaign.starts_at),
                "end_at": str(campaign.ends_at),
                "image_url": campaign.image_url
            })
        return web.json_response(inventory_data)
