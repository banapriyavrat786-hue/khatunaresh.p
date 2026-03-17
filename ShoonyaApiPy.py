import requests
import json
import logging

class ShoonyaApiPy:
    def __init__(self, host=None, websocket=None):
        self._host = host or "https://api.shoonya.com/NorenWSTP/"
        self._session = requests.Session()

    def login(self, userid, password, twoFA, vendor_code, api_key):
        url = self._host + "QuickAuth"
        payload = {"source": "API", "userid": userid, "password": password, "twoFA": twoFA, "vcode": vendor_code, "appkey": api_key}
        res = self._session.post(url, data=f"jData={json.dumps(payload)}&jKey=")
        res_dict = res.json()
        if res_dict.get('stat') == 'Ok':
            self._session.headers.update({"Authorization": f"Bearer {res_dict['susertoken']}"})
        return res_dict

    def get_quotes(self, exchange, token):
        url = self._host + "GetQuotes"
        payload = {"uid": self._session.headers.get("Authorization"), "exch": exchange, "token": token}
        res = self._session.post(url, data=f"jData={json.dumps(payload)}")
        return res.json()
