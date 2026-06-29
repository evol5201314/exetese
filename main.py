import requests
import time

# ========== 自定义配置区 ==========
PUSH_TOKEN = "cdc7db6c36da46c1b877543016be3cba"
TIMEOUT = 12
# 黄金数据源
API_LIST = [
    "https://api.freejk.com/shuju/jinjia/",
    "https://xaus.com/api/v1/spot",
    "https://freegoldapi.com/data/latest.json"
]
ETF_CODE = "518880"
ETF_GRAM_PER_SHARE = 0.01
# A股/场内基金列表，只保留黄金ETF，删除比亚迪、招行
STOCK_CODES = "518880"
# ==================================

def push_wechat(title, content):
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
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    }
    for api in API_LIST:
        try:
            resp = requests.get(api, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if "freejk" in api:
                usd_oz = round(data["data"]["international_price"], 2)
                cny_gram = round(data["data"]["price"], 2)
                usd_cny = round((data["data"]["price"] * 31.1035) / data["data"]["international_price"], 4)
                return {
                    "usd_oz": usd_oz,
                    "cny_gram": cny_gram,
                    "usd_cny_rate": usd_cny,
                    "source": "freejk国内行情"
                }
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
            elif "freegoldapi" in api:
                last_item = data[-1]
                usd_oz = round(last_item["price"], 2)
                usd_cny = 7.22
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
    raise Exception("所有金价接口均访问失败，请检查容器网络")

def get_stock_info(code_str):
    """A股/基金统一行情文本，新增昨日涨幅字段"""
    code_list = code_str.split()
    line_list = []
    code_param = ""
    for code in code_list:
        if code.startswith("6"):
            code_param += f"sh{code},"
        else:
            code_param += f"sz{code},"
    code_param = code_param.rstrip(",")
    url = f"http://hq.sinajs.cn/list={code_param}"
    headers = {"User-Agent": "Mozilla/5.0 Python Script", "Referer": "http://finance.sina.com.cn"}
    try:
        res = requests.get(url, headers=headers, timeout=TIMEOUT)
        raw_text = res.text
        lines = raw_text.strip().split(";")
        for line in lines:
            if not line:
                continue
            data_part = line.split('"')[1]
            arr = data_part.split(",")
            if len(arr) < 30:
                continue
            name = arr[0]
            now = float(arr[3])
            last_close = float(arr[2])
            yesterday_price = float(arr[1])
            change = round(now - last_close, 2)
            change_pct = round((change / last_close) * 100, 2)
            last_day_change = round(last_close - yesterday_price, 2)
            last_day_pct = round((last_day_change / yesterday_price) * 100, 2)
            code = line.split("=")[0].split("_")[-1]
            # 统一格式：增加昨日涨跌、昨日涨幅
            line_list.append(f"{code} {name}")
            line_list.append(f"当前价位：{now} 元")
            line_list.append(f"昨日收盘：{last_close} 元")
            line_list.append(f"当日涨跌：{change} 元（{change_pct}%）")
            line_list.append(f"昨日涨跌：{last_day_change} 元（{last_day_pct}%）")
            line_list.append("-" * 30)
    except Exception as e:
        line_list.append(f"A股行情获取失败：{str(e)}")
    return "\n".join(line_list)

def get_us_index(usd_rate):
    """纳指、标普500，统一格式+换算人民币点位+昨日涨幅"""
    index_codes = ["int_nasdaq", "int_sp500"]
    url = f"http://hq.sinajs.cn/list={','.join(index_codes)}"
    headers = {"User-Agent": "Mozilla/5.0 Python Script", "Referer": "http://finance.sina.com.cn"}
    line_list = []
    try:
        res = requests.get(url, headers=headers, timeout=TIMEOUT)
        raw = res.text.strip().split(";")
        for line in raw:
            if not line:
                continue
            data = line.split('"')[1].split(",")
            idx_name = data[0]
            now = float(data[1])
            change = float(data[2])
            change_pct = float(data[3])
            last_close = round(now - change, 2)
            yesterday_point = float(data[4])
            last_day_change = round(last_close - yesterday_point, 2)
            last_day_pct = round((last_day_change / yesterday_point) * 100, 2)
            cny_price = round(now * usd_rate, 2)
            line_list.append(f"{idx_name}")
            line_list.append(f"当前价位：{now} 点（折合人民币 {cny_price}）")
            line_list.append(f"昨日收盘：{last_close} 点")
            line_list.append(f"当日涨跌：{change} 点（{change_pct}%）")
            line_list.append(f"昨日涨跌：{last_day_change} 点（{last_day_pct}%）")
            line_list.append("-" * 30)
    except Exception as e:
        line_list.append(f"美股指数获取失败：{str(e)}")
    return "\n".join(line_list)

if __name__ == "__main__":
    try:
        gold_data = get_gold_data()
        usd_cny_rate = gold_data["usd_cny_rate"]
        gram_price = gold_data["cny_gram"]
        etf_price = round(gram_price * ETF_GRAM_PER_SHARE, 2)

        # 黄金板块统一格式
        gold_block = [
            "【黄金行情】",
            f"数据源：{gold_data['source']}",
            f"伦敦金现价：{gold_data['usd_oz']} 美元/盎司",
            f"美元兑人民币汇率：1USD = {usd_cny_rate}",
            f"国内金价：{gram_price} 元/克",
            f"{ETF_CODE}华安黄金ETF理论价：{etf_price} 元/份",
            "-" * 30
        ]
        gold_text = "\n".join(gold_block)

        # A股板块（仅保留518880）
        stock_text = "【A股/场内基金行情】\n" + get_stock_info(STOCK_CODES)

        # 美股指数板块
        us_text = "【美股宽基指数行情】\n" + get_us_index(usd_cny_rate)

        full_msg = f"{gold_text}\n\n{stock_text}\n\n{us_text}"
        push_wechat("黄金+A股+纳指+标普500统一行情播报", full_msg)
        print("推送完成")
        print(full_msg)
    except Exception as err:
        err_msg = f"行情脚本异常：{str(err)}"
        push_wechat("行情脚本异常提醒", err_msg)
        print(err_msg)
