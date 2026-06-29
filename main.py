"""
===== 【OpenWrt 低内存专用优化说明 请勿删除以下轻量化逻辑】
硬件环境：路由可用内存仅≈50M，精简python，峰值内存控制≤13M
"""
import requests, time, gc, os, sys
beizhu = "📈 监控股价"
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

requests.adapters.DEFAULT_RETRIES = 0
SESS = requests.Session()
SESS.keep_alive = False
GLOBAL_TIMEOUT = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 Linux Chrome/124.0 Safari/537.36",
    "Connection": "close"
}

# ====================== 顶部配置区 ======================
PUSH_TOKEN = "cdc7db6c36da46c1b877543016be3cba"
STOCK_LIST = [
    "518880",
]
US_INDEX_LIST = ["int_nasdaq", "int_sp500"]
CRYPTO_LIST = ["BTC", "ETH"]
API_LIST = [
    "https://api.freejk.com/shuju/jinjia/",
    "https://xaus.com/api/v1/spot",
    "https://freegoldapi.com/data/latest.json"
]
ETF_CODE = "518880"
ETF_GRAM_PER_SHARE = 0.01
# =======================================================================

# 常量优化：避免重复计算分隔线
SEP_LINE = "----------------------------------------"
SEP_SHORT = "-" * 30

def push_wechat(title, content):
    try:
        SESS.post(
            "http://www.pushplus.plus/send",
            json={"token": PUSH_TOKEN, "title": title, "content": content},
            timeout=GLOBAL_TIMEOUT,
            headers=HEADERS
        )
    except Exception:
        pass

def get_gold_data():
    for api in API_LIST:
        try:
            resp = SESS.get(api, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            del resp
            if "freejk" in api:
                oz = round(data["data"]["international_price"], 2)
                gram = round(data["data"]["price"], 2)
                rate = round((gram * 31.1035) / oz, 4)
                res = {"usd_oz": oz, "cny_gram": gram, "usd_cny_rate": rate, "source": "freejk国内行情"}
            elif "xaus" in api:
                oz = round(data["spot_usd_oz"], 2)
                rate = round(data["currency_rates"]["USD_CNY"], 4)
                gram = round((oz * rate) / 31.1035, 2)
                res = {"usd_oz": oz, "cny_gram": gram, "usd_cny_rate": rate, "source": "xaus国际现货"}
            else:
                last_item = data[-1]
                oz = round(last_item["price"], 2)
                rate, gram = 7.22, round((oz * rate) / 31.1035, 2)
                res = {"usd_oz": oz, "cny_gram": gram, "usd_cny_rate": rate, "source": "freegold兜底数据源"}
            del data
            return res
        except Exception:
            time.sleep(0.5)
    raise Exception("全部金价接口请求超时/失败")

def get_stock_info(code_list):
    code_param = ""
    for code in code_list:
        code_param += f"sh{code}," if code.startswith("6") else f"sz{code},"
    code_param = code_param.rstrip(",")
    url = f"http://hq.sinajs.cn/list={code_param}"
    buf = []
    try:
        r = SESS.get(url, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
        raw_text = r.text
        del r
        for line in raw_text.split(";"):
            line = line.strip()
            if not line or '="' not in line:
                continue
            left, data_str = line.split('"', 1)
            data_str = data_str.rstrip('"')
            arr = data_str.split(",")
            stock_code = left.split("_")[-1]
            name = arr[0] if len(arr) >= 1 else "未知标的"
            last_close = float(arr[2]) if len(arr) >= 3 else 0.0
            now_price = float(arr[3]) if len(arr) >= 4 else 0.0
            change = round(now_price - last_close, 2) if last_close != 0 else 0.0
            change_pct = round((change / last_close) * 100, 2) if last_close != 0 else 0.0
            buf.append(f"【{stock_code} {name}】")
            buf.append(f"现价：{now_price} 元")
            buf.append(f"昨收：{last_close} 元")
            buf.append(f"当日涨跌：{change} 元（{change_pct}%）")
            buf.append(SEP_LINE)
        del raw_text
    except Exception as e:
        buf.append(f"股票接口整体请求失败：{e}")
    return "\n".join(buf)

# 美股指数优化：复用全局SESS，避免新建Session
def get_us_index(rate, idx_list):
    US_TIMEOUT = 12
    us_headers = {**HEADERS, "Referer": "http://finance.sina.com.cn"}
    url = f"http://hq.sinajs.cn/list={','.join(idx_list)}"
    buf = []
    try:
        r = SESS.get(url, headers=us_headers, timeout=US_TIMEOUT)
        content = r.text
        del r
        for line in content.split(";"):
            line = line.strip()
            if not line or '="' not in line:
                continue
            raw_str = line.split('"')[1]
            data = raw_str.split(",")
            if len(data) < 4:
                buf.extend(["指数数据残缺，跳过", SEP_SHORT])
                continue
            try:
                idx_name = data[0]
                now = float(data[1])
                change = float(data[2])
                change_pct = float(data[3])
                yesterday_point = float(data[4]) if len(data) >= 5 else now
            except ValueError:
                buf.extend([f"{data[0]} 数值解析失败", SEP_SHORT])
                continue
            last_close = round(now - change, 2)
            day_chg = round(last_close - yesterday_point, 2)
            day_pct = round((day_chg / yesterday_point) * 100, 2) if yesterday_point != 0 else 0
            rmb_price = round(now * rate, 2)
            buf += [
                idx_name,
                f"点位：{now} | 折合人民币{rmb_price}",
                f"昨收：{last_close} 点",
                f"当日涨跌：{change}点（{change_pct}%）",
                f"前日涨跌：{day_chg}点（{day_pct}%）",
                SEP_SHORT
            ]
        del content
    except Exception as e:
        buf.append(f"美股指数接口失败：{e}")
    return "\n".join(buf)

def get_crypto_info(coin_list, usd_rate):
    buf = []
    base_url = "https://www.okx.com/api/v5/market/ticker"
    for coin in coin_list:
        inst_id = f"{coin}-USDT"
        try:
            resp = SESS.get(f"{base_url}?instId={inst_id}", headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            json_data = resp.json()
            del resp
            data = json_data["data"][0]
            sym = coin
            usd_now = round(float(data["last"]), 2)
            usd_today_open = round(float(data["sodUtc8"]), 2)
            usd_24h_open = round(float(data["open24h"]), 2)
            cny_now = round(usd_now * usd_rate, 2)
            cny_today_open = round(usd_today_open * usd_rate, 2)
            today_chg_usd = round(usd_now - usd_today_open, 2)
            today_chg_pct = round((today_chg_usd / usd_today_open) * 100, 2) if usd_today_open else 0
            chg_24h_usd = round(usd_now - usd_24h_open, 2)
            chg_24h_pct = round((chg_24h_usd / usd_24h_open) * 100, 2) if usd_24h_open else 0
            usd_yesterday_close = usd_today_open
            usd_yesterday_open = round(2 * usd_24h_open - usd_today_open, 2)
            yesterday_chg_usd = round(usd_yesterday_close - usd_yesterday_open, 2)
            yesterday_chg_pct = round((yesterday_chg_usd / usd_yesterday_open) * 100, 2) if usd_yesterday_open else 0
            cny_yesterday_close = round(usd_yesterday_close * usd_rate, 2)

            buf += [
                sym,
                f"现价：${usd_now} | 折合人民币¥{cny_now}",
                f"今日开盘(早8点)：${usd_today_open} 折合¥{cny_today_open}",
                f"昨日收盘：${usd_yesterday_close} 折合¥{cny_yesterday_close}",
                f"今日涨幅：${today_chg_usd}（{today_chg_pct}%）",
                f"昨日涨幅：${yesterday_chg_usd}（{yesterday_chg_pct}%）",
                f"24小时涨幅：{chg_24h_pct}%",
                SEP_LINE
            ]
            del json_data, data
        except Exception:
            buf.append(f"{coin} OKX欧易接口访问失败")
            buf.append(SEP_LINE)
            time.sleep(0.3)
    return "\n".join(buf)

if __name__ == "__main__":
    try:
        gold_info = get_gold_data()
        usd_ex = gold_info["usd_cny_rate"]
        gram_price = gold_info["cny_gram"]
        etf_price = round(gram_price * ETF_GRAM_PER_SHARE, 2)
        gold_text = "\n".join([
            "===== 黄金行情 =====",
            f"数据源：{gold_info['source']}",
            f"伦敦金：{gold_info['usd_oz']} 美元/盎司",
            f"美元汇率：1USD = {usd_ex}",
            f"国内金价：{gram_price} 元/克",
            f"{ETF_CODE}理论净值：{etf_price} 元/份",
            SEP_LINE
        ])
        del gold_info

        try:
            us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_ex, US_INDEX_LIST)
        except Exception as us_err:
            us_text = f"===== 美股宽基指数 =====\n美股整体获取异常：{str(us_err)}"

        crypto_text = "===== 虚拟币行情 =====\n" + get_crypto_info(CRYPTO_LIST, usd_ex)

        # 直接推送，不保留中间拼接变量，推送后内容即被释放
        push_wechat("黄金+美股+BTC/ETH行情播报", f"{gold_text}\n{us_text}\n{crypto_text}")

        # 最终清理，仅一次gc即可
        del gold_text, us_text, crypto_text
        gc.collect()

    except Exception as err:
        push_wechat("行情脚本异常提醒", f"脚本全局异常：{str(err)}")
