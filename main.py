import requests, time, gc, os, sys
# 屏蔽全部控制台打印，输出丢黑洞，不擦写路由闪存
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 网络全局配置：8秒单次超时、关闭长连接、无重试防卡死
requests.adapters.DEFAULT_RETRIES = 0
SESS = requests.Session()
SESS.keep_alive = False
GLOBAL_TIMEOUT = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 Linux Chrome/124.0 Safari/537.36",
    "Referer": "http://finance.sina.com.cn",
    "Connection": "close"
}

# ====================== 【所有标的增删统一在顶部，不用修改下方函数】 ======================
PUSH_TOKEN = "cdc7db6c36da46c1b877543016be3cba"
# 1、A股/场内基金 新增股票写这里
STOCK_LIST = [
    "518880",
    # "600036",
    # "002594"
]
# 2、美股指数 新增指数写这里
US_INDEX_LIST = ["int_nasdaq", "int_sp500"]
# 3、虚拟币 BTC/ETH/SOL 新增币种写这里【你要的新增虚拟币位置】
CRYPTO_LIST = ["bitcoin", "ethereum"]
# 4、黄金行情备用接口新增位置
API_LIST = [
    "https://api.freejk.com/shuju/jinjia/",
    "https://xaus.com/api/v1/spot",
    "https://freegoldapi.com/data/latest.json"
]
ETF_CODE, ETF_GRAM_PER_SHARE = "518880", 0.01
# =======================================================================================

# 微信推送函数（原版完整保留，无删减）
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
    gc.collect()

# 黄金数据获取函数 原版完整保留
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
            gc.collect()
            return res
        except Exception:
            time.sleep(0.8)
            gc.collect()
    raise Exception("全部金价接口请求超时/失败")

# A股股票解析函数【完整保留，没有删除】，启用股票推送只需打开主程序注释
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
            name = "未知标的"
            now_price = 0.0
            last_close = 0.0
            change = 0.0
            change_pct = 0.0
            if len(arr) >= 1:
                name = arr[0]
            if len(arr) >= 3:
                try:
                    last_close = float(arr[2])
                except:
                    pass
            if len(arr) >= 4:
                try:
                    now_price = float(arr[3])
                except:
                    pass
            if last_close != 0:
                change = round(now_price - last_close, 2)
                change_pct = round((change / last_close) * 100, 2)
            buf.append(f"【{stock_code} {name}】")
            buf.append(f"现价：{now_price} 元")
            buf.append(f"昨收：{last_close} 元")
            buf.append(f"当日涨跌：{change} 元（{change_pct}%）")
            buf.append("----------------------------------------")
        del raw_text
    except Exception as e:
        buf.append(f"股票接口整体请求失败：{e}")
    gc.collect()
    return "\n".join(buf)

# 美股指数函数 原版完整保留
def get_us_index(rate, idx_list):
    buf = []
    url = f"http://hq.sinajs.cn/list={','.join(idx_list)}"
    try:
        resp = SESS.get(url, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
        text_lines = resp.text.split(";")
        del resp
        for line in text_lines:
            line = line.strip()
            if not line or '="' not in line:
                continue
            field_arr = line.split('"')[1].split(",")
            if len(field_arr) < 4:
                buf.extend(["指数数据残缺，跳过", "----------------------------------------"])
                continue
            try:
                idx_name, now, chg, chg_pct, yest_pt = field_arr[0], float(field_arr[1]), float(field_arr[2]), float(field_arr[3]), float(field_arr[4]) if len(field_arr)>=5 else float(field_arr[1])
            except Exception:
                buf.extend([f"{field_arr[0]}数值解析失败", "----------------------------------------"])
                continue
            last_close = round(now - chg, 2)
            day_chg = round(last_close - yest_pt, 2)
            day_pct = round((day_chg / yest_pt)*100, 2) if yest_pt != 0 else 0
            rmb_price = round(now * rate, 2)
            buf += [
                idx_name,
                f"点位：{now} | 折合人民币{rmb_price}",
                f"昨收：{last_close} 点",
                f"当日涨跌：{chg}点（{chg_pct}%）",
                f"前日涨跌：{day_chg}点（{day_pct}%）",
                "----------------------------------------"
            ]
        del text_lines
    except Exception:
        buf.append("美股指数接口请求失败")
    gc.collect()
    return "\n".join(buf)

# 虚拟币行情函数 原版完整保留，字段：现价/昨收/当日涨跌/昨日涨幅/24小时涨幅
def get_crypto_info(coin_list, usd_rate):
    buf = []
    coin_ids = ",".join(coin_list)
    domain_pool = ["https://api.coingecko.com/api/v3", "https://pro-api.coingecko.com/api/v3"]
    target_resp = None
    for domain in domain_pool:
        try:
            req_url = f"{domain}/coins/markets?vs_currency=usd&ids={coin_ids}&order=market_cap_desc&price_change_percentage=24h"
            target_resp = SESS.get(req_url, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            target_resp.raise_for_status()
            break
        except Exception:
            time.sleep(0.8)
    if not target_resp:
        buf.append("虚拟币全部接口访问失败")
        gc.collect()
        return "\n".join(buf)
    coin_data = target_resp.json()
    del target_resp
    for coin in coin_data:
        sym = coin["symbol"].upper()
        usd_now = round(coin["current_price"], 2)
        usd_yest = round(usd_now - coin["price_change_24h"], 2)
        usd_before_yest = round(usd_yest - (coin["price_change_24h"] / (1 + coin["price_change_percentage_24h"] / 100)), 2)
        cny_now, cny_yest = round(usd_now * usd_rate, 2), round(usd_yest * usd_rate, 2)
        chg_now_usd = round(coin["price_change_24h"], 2)
        chg_now_pct = round(coin["price_change_percentage_24h"], 2)
        chg_prev_usd = round(usd_yest - usd_before_yest, 2)
        chg_prev_pct = round((chg_prev_usd / usd_before_yest)*100, 2) if usd_before_yest != 0 else 0
        pct_24h = round(coin["price_change_percentage_24h"], 2)
        buf += [
            f"{sym}",
            f"现价：${usd_now} | 折合人民币¥{cny_now}",
            f"昨收：${usd_yest} 折合¥{cny_yest}",
            f"当日涨跌：${chg_now_usd}（{chg_now_pct}%）",
            f"昨日涨幅：${chg_prev_usd}（{chg_prev_pct}%）",
            f"24小时涨幅：{pct_24h}%",
            "----------------------------------------"
        ]
    del coin_data
    gc.collect()
    return "\n".join(buf)

# 进程自销毁：执行完毕强制kill python进程，RAM完全释放，后台无残留
def kill_self():
    try:
        current_pid = os.getpid()
        os.system(f"kill -9 {current_pid}")
        os.system("pkill -f python3 2>/dev/null || pkill -f python 2>/dev/null")
    except Exception:
        pass

# 单次执行入口，无循环、无后台常驻
if __name__ == "__main__":
    try:
        gold_info = get_gold_data()
        usd_ex = gold_info["usd_cny_rate"]
        gram_price = gold_info["cny_gram"]
        etf_price = round(gram_price * ETF_GRAM_PER_SHARE, 2)
        gold_block = [
            "===== 黄金行情 =====",
            f"数据源：{gold_info['source']}",
            f"伦敦金：{gold_info['usd_oz']} 美元/盎司",
            f"美元汇率：1USD = {usd_ex}",
            f"国内金价：{gram_price} 元/克",
            f"{ETF_CODE}理论净值：{etf_price} 元/份",
            "----------------------------------------"
        ]
        gold_text = "\n".join(gold_block)
        us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_ex, US_INDEX_LIST)
        crypto_text = "===== 虚拟币行情 =====\n" + get_crypto_info(CRYPTO_LIST, usd_ex)

        # ============ 开启股票推送请取消下面两行注释 ============
        # stock_text = "===== 持仓股票行情 =====\n" + get_stock_info(STOCK_LIST)
        # full_msg = f"{gold_text}\n{stock_text}\n{us_text}\n{crypto_text}"

        # 当前默认推送：黄金 + 美股 + 虚拟币（不输出股票）
        full_msg = f"{gold_text}\n{us_text}\n{crypto_text}"
        push_wechat("黄金+美股+BTC/ETH行情播报", full_msg)

        # 内存手动回收
        del gold_info, gold_text, us_text, crypto_text, full_msg, gold_block
        gc.collect()
    except Exception:
        push_wechat("行情脚本异常提醒", "脚本运行过程中出现未知错误")
        gc.collect()
    # 无论成功失败，强制销毁进程
    kill_self()
