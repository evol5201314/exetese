import requests
import time

# ====================== 【顶部统一配置区，全部在这里增删】 ======================
PUSH_TOKEN = "cdc7db6c36da46c1b877543016be3cba"
TIMEOUT = 12

# 1. A股/场内基金列表，新增直接往里加，自动区分沪sh/深sz
STOCK_LIST = [
    "518880",
    # "600036",
    # "000001",
    # "300750"
]

# 2. 美股指数列表，想加其他指数直接填编码
US_INDEX_LIST = [
    "int_nasdaq",    # 纳斯达克
    "int_sp500"      # 标普500
    # "int_dji"       # 道琼斯（需要取消注释即可使用）
]

# 黄金行情配置
API_LIST = [
    "https://api.freejk.com/shuju/jinjia/",
    "https://xaus.com/api/v1/spot",
    "https://freegoldapi.com/data/latest.json"
]
ETF_CODE = "518880"
ETF_GRAM_PER_SHARE = 0.01

# 全局请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 Linux Chrome/124.0 Safari/537.36",
    "Referer": "http://finance.sina.com.cn"
}
# ==============================================================================

# 微信推送
def push_wechat(title, content):
    try:
        requests.post(
            "http://www.pushplus.plus/send",
            json={"token": PUSH_TOKEN, "title": title, "content": content},
            timeout=10
        )
    except Exception as e:
        print("推送失败:", e)

# 多接口轮询获取金价
def get_gold_data():
    for api in API_LIST:
        try:
            r = requests.get(api, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            d = r.json()
            if "freejk" in api:
                oz = round(d["data"]["international_price"], 2)
                g = round(d["data"]["price"], 2)
                rate = round((g * 31.1035) / oz, 4)
                return {"usd_oz":oz, "cny_gram":g, "usd_cny_rate":rate, "source":"freejk国内行情"}
            elif "xaus" in api:
                oz = round(d["spot_usd_oz"], 2)
                rate = round(d["currency_rates"]["USD_CNY"], 4)
                g = round((oz * rate) / 31.1035, 2)
                return {"usd_oz":oz, "cny_gram":g, "usd_cny_rate":rate, "source":"xaus国际现货"}
            elif "freegoldapi" in api:
                last = d[-1]
                oz = round(last["price"], 2)
                rate = 7.22
                g = round((oz * rate) / 31.1035, 2)
                return {"usd_oz":oz, "cny_gram":g, "usd_cny_rate":rate, "source":"freegold兜底数据源"}
        except Exception as e:
            print(f"{api} 请求异常: {e}")
            time.sleep(1)
    raise Exception("所有金价接口全部失效")

# 批量获取A股行情，自动判断沪/深市场
def get_stock_info(code_list):
    code_param = ""
    for code in code_list:
        if code.startswith("6"):
            code_param += f"sh{code},"
        else:
            code_param += f"sz{code},"
    code_param = code_param.rstrip(",")
    url = f"http://hq.sinajs.cn/list={code_param}"
    buf = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        for line in r.text.split(";"):
            line = line.strip()
            if not line or '="' not in line:
                continue
            data_part = line.split('"')[1]
            arr = data_part.split(",")
            if len(arr) < 30:
                buf.append("个股数据残缺，读取失败")
                buf.append("-" * 30)
                continue
            stock_code = line.split("=")[0].split("_")[-1]
            name = arr[0]
            now_price = float(arr[3])    # 当前价位
            last_close = float(arr[2])   # 昨日价位
            change = round(now_price - last_close, 2)  # 今日涨跌金额
            change_pct = round((change / last_close) * 100, 2) # 今日涨跌幅

            buf.append(f"【{stock_code} {name}】")
            buf.append(f"现价：{now_price} 元")
            buf.append(f"昨收：{last_close} 元")
            buf.append(f"今日涨跌：{change} 元（{change_pct}%）")
            buf.append("-" * 30)
    except Exception as e:
        buf.append(f"股票接口请求失败：{e}")
    return "\n".join(buf)

# 读取顶部US_INDEX_LIST批量获取美股指数，容错拉满
def get_us_index(rate, index_list):
    code_str = ",".join(index_list)
    url = f"http://hq.sinajs.cn/list={code_str}"
    buf = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        content = r.text
        for line in content.split(";"):
            line = line.strip()
            if not line or '="' not in line:
                continue
            raw_str = line.split('"')[1]
            data = raw_str.split(",")
            if len(data) < 4:
                buf.extend(["指数数据残缺，跳过", "-"*30])
                continue
            try:
                idx_name = data[0]
                now = float(data[1])
                change = float(data[2])
                change_pct = float(data[3])
                yesterday_point = float(data[4]) if len(data)>=5 else now
            except ValueError:
                buf.extend([f"{data[0]} 数值解析失败", "-"*30])
                continue
            last_close = round(now - change, 2)
            day_chg = round(last_close - yesterday_point, 2)
            day_pct = round((day_chg / yesterday_point)*100, 2) if yesterday_point !=0 else 0
            rmb_price = round(now * rate, 2)
            buf += [
                idx_name,
                f"点位：{now} | 折合人民币{rmb_price}",
                f"昨收：{last_close} 点",
                f"当日涨跌：{change}点（{change_pct}%）",
                f"前日涨跌：{day_chg}点（{day_pct}%）",
                "-"*30
            ]
    except Exception as e:
        buf.append(f"美股指数接口失败：{e}")
    return "\n".join(buf)

if __name__ == "__main__":
    try:
        # 获取黄金行情
        gold_data = get_gold_data()
        usd_rate = gold_data["usd_cny_rate"]
        gram_price = gold_data["cny_gram"]
        etf_theory = round(gram_price * ETF_GRAM_PER_SHARE, 2)

        gold_text = "\n".join([
            "===== 黄金行情 =====",
            f"数据源：{gold_data['source']}",
            f"伦敦金：{gold_data['usd_oz']} 美元/盎司",
            f"美元汇率：1USD = {usd_rate}",
            f"国内金价：{gram_price} 元/克",
            f"{ETF_CODE}理论净值：{etf_theory} 元/份",
            "-" * 40
        ])

        # A股行情（读取顶部STOCK_LIST）
        stock_text = "===== 持仓股票行情 =====\n" + get_stock_info(STOCK_LIST)

        # 美股指数（读取顶部US_INDEX_LIST）
        us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_rate, US_INDEX_LIST)

        full_msg = f"{gold_text}\n{stock_text}\n{us_text}"
        push_wechat("黄金+持仓股票+美股每日行情播报", full_msg)
        print("推送完成！\n", full_msg)

    except Exception as err:
        err_msg = f"脚本全局异常：{str(err)}"
        push_wechat("行情脚本异常提醒", err_msg)
        print(err_msg)
