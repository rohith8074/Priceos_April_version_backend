import os
import httpx
from typing import Dict, Any, Optional

BASE_URL = 'https://crap0y5bx5.execute-api.us-east-2.amazonaws.com/prod'

def get_api_key() -> str:
    key = os.environ.get("AIRBTICS_API_KEY")
    if not key:
        raise ValueError("AIRBTICS_API_KEY is not defined")
    return key

async def get(path: str, params: Optional[Dict[str, str]] = None) -> Any:
    if params is None:
        params = {}
    
    headers = {'x-api-key': get_api_key()}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}{path}", params=params, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Airbtics {response.status_code}: {path} - {response.text}")
        return response.json()

class AirbticsService:
    @staticmethod
    async def search_market(query: str, country_code: str):
        return await get('/markets/search', {'query': query, 'country_code': country_code})
    
    @staticmethod
    async def get_market_summary(market_id: str, bedrooms: str):
        return await get('/markets/summary', {'market_id': market_id, 'bedrooms': bedrooms})

    @staticmethod
    async def get_market_metrics(market_id: str, bedrooms: str, months: str = '12'):
        return await get('/markets/metrics/all', {
            'market_id': market_id, 
            'bedrooms': bedrooms, 
            'number_of_months': months
        })
    
    @staticmethod
    async def get_future_pacing(market_id: str, bedrooms: str):
        return await get('/markets/metrics/future-pacing', {
            'market_id': market_id, 
            'bedrooms': bedrooms
        })

    @staticmethod
    async def search_listings_by_bounds(bounds: Dict[str, float], bedrooms: int):
        headers = {
            'x-api-key': get_api_key(),
            'Content-Type': 'application/json'
        }
        payload = {
            "bounds": bounds,
            "bedrooms": bedrooms,
            "page": 1
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/listings/search/bounds", json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"Airbtics {response.status_code}: /listings/search/bounds - {response.text}")
            return response.json()

    @staticmethod
    async def generate_revenue_report(lat: float, lng: float, bedrooms: int):
        headers = {
            'x-api-key': get_api_key(),
            'Content-Type': 'application/json'
        }
        payload = {
            "latitude": lat,
            "longitude": lng,
            "bedrooms": bedrooms
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/report/all", json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"Airbtics {response.status_code}: /report/all - {response.text}")
            return response.json()

    @staticmethod
    async def get_report(report_id: str):
        return await get('/report', {'report_id': report_id})
