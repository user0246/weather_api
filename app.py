from fastapi import FastAPI, HTTPException, Request
import requests
import redis
import json


app = FastAPI()

r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

@app.get("/weather")
def weather(request: Request, city: str):
    params = {
        "key": "YOUR_API_KEY",
        "unitGroup": "metric"
    }

    cache_key = f"weather:{city.strip().lower()}"
    rate_limit_key = f"rate_limit:{request.client.host}"
    
    counter_for_requests = r.incr(rate_limit_key, amount=1)
    if counter_for_requests == 1:
        r.expire(rate_limit_key, 60)
    elif counter_for_requests > 10:
        raise HTTPException(status_code=429, detail="out of requests")

    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city}"

    redis_weather = r.get(cache_key)

    if redis_weather is not None:
        print("redis data")

        return json.loads(redis_weather) 
    else:
        print("weather api data")
        try:
            response = requests.get(url, timeout=10, params=params)
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="weather api timeout")
        except requests.exceptions.ConnectionError:
            raise HTTPException(status_code=502, detail="connection error")

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="city not found or something else") 

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            raise HTTPException(status_code=502, detail="cannot convert to json")

        weather_data = {
            "city": city,
            "temperature": data["currentConditions"]["temp"],
            "humidity": data["currentConditions"]["humidity"]
        }

        r.set(cache_key, json.dumps(weather_data), ex=600)

        return weather_data 