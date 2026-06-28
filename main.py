import requests
import time

# ========== 配置区 ==========
PUSH_TOKEN = "cdc7db6c36da46c1b877543016be3cba"
TIMEOUT = 12  # 单接口超时秒数
# 三路备用接口，自动切换
API_LIST = [
    "https://api.freejk.com/shuju/jinjia/",
    "https://xaus.com/api/v1/spot",
    "https://freegoldapi.com/data/latest.json"
]
# ==========================

def push_wechat(title, content):
    """PushPlus微信推送"""
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSH_TOKEN,
        "title": title,
        "content": content
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("推送失败：", str(e))

def get_gold_data():
    """轮询多接口获取金价，任一成功直接返回"""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    }
    for api in API_LIST:
        try:
            resp = requests.get(api, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            # 分支1：国内freejk接口（含人民币国际金价）
            if "freejk" in api:
                usd_oz = round(data["data"]["international_price"], 2)
                cny_gram = round(data["data"]["price"], 2)
                rate = round(data["data"]["international_price"] / (data["data"]["price"] * 31.1035), 4)
                return {
                    "usd_oz": usd_oz,
                    "cny_gram": cny_gram,
                    "usd_cny_rate": rate,
                    "source": "freejk国内行情"
                }
            # 分支2：xaus海外接口
            elif "xaus" in api:
                usd_oz = round(data["spot_usd_oz"], 2)
                usd_cny = round(data["currency_rates"]["USD_CNY"], 4)
                cny_oz = round(usd_oz * usd_cny, 2)
                cny_gram = round(cny_oz / 31.1035, 2)
                return {
                    "usd_oz": usd_oz,
                    "cny_gram": cny_gram,
                    "usd_cny_rate": usd_cny,
                    "source": "xaus国际现货"
                }
            # 分支3：freegoldapi兜底
            elif "freegoldapi" in api:
                last_item = data[-1]
                usd_oz = round(last_item["price"], 2)
                usd_cny = 7.22  # 兜底固定汇率，防止接口无汇率
                cny_oz = round(usd_oz * usd_cny, 2)
                cny_gram = round(cny_oz / 31.1035, 2)
                return {
                    "usd_oz": usd_oz,
                    "cny_gram": cny_gram,
                    "usd_cny_rate": usd_cny,
                    "source": "freegold兜底数据源"
                }
        except Exception as e:
            print(f"接口 {api} 请求失败，切换下一个，错误：{str(e)}")
            time.sleep(1)
    # 全部接口失效
    raise Exception("所有金价接口均访问失败，请检查容器网络")

if __name__ == "__main__":
    try:
        res = get_gold_data()
        msg = f"""
【手动查询·实时黄金行情】
数据来源：{res['source']}
伦敦金 XAUUSD：{res['usd_oz']} 美元/盎司
美元兑人民币：1USD = {res['usd_cny_rate']} CNY
折合人民币：{res['cny_gram']} 元/克
换算标准：1盎司=31.1035克
        """.strip()
        push_wechat("黄金实时报价", msg)
        print("查询成功，微信推送已发送")
        print(msg)
    except Exception as err:
        err_text = f"金价查询全部接口失败：{str(err)}"
        push_wechat("金价脚本异常提醒", err_text)
        print(err_text)
