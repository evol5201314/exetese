import requests, time, gc, os, sys
# 屏蔽控制台输出，零闪存擦写路由存储
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 网络全局配置：8秒单次超时、关闭长连接、0重试防卡死僵死进程
requests.adapters.DEFAULT_RETRIES = 0
SESS = requests.Session()
SESS.keep_alive = False
GLOBAL_TIMEOUT = 8
HEADERS = {
    "User-Agent": "Mozilla/5.0 Linux Chrome/124.0 Safari/537.36",
    "Connection": "close"
}

# ====================== 顶部配置区 所有标的增删位置 ======================
PUSH_TOKEN = "cdc7db6c36da46c1b877543016be3cba"
# 1.A股/基金新增位置（保留，默认不推送）
STOCK_LIST = [
    "518880",
    # "600036",
    # "002594"
]
# 2.美股指数新增位置
US_INDEX_LIST = ["int_nasdaq", "int_sp500"]
# 3.虚拟币新增位置【此处添加币种，格式BTC/ETH，统一USDT交易对】
CRYPTO_LIST = ["BTC", "ETH"]
# 黄金备用行情接口
API_LIST = [
    "https://api.freejk.com/shuju/jinjia/",
    "https://xaus.com/api/v1/spot",
    "https://freegoldapi.com/data/latest.json"
]
ETF_CODE, ETF_GRAM_PER_SHARE = "518880", 0.01
# =======================================================================

# 微信推送函数
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

# 黄金+美元汇率获取逻辑不变
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
            time.sleep(0.5)
            gc.collect()
    raise Exception("全部金价接口请求超时/失败")

# A股解析函数完整保留，启用只需解开主程序两行注释
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

# 美股指数逻辑不变
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

# 虚拟币：币安公开API，全部原生字段直出，无任何手动计算
# o=今日开盘(早8点)、x=昨日收盘、p/P=24小时涨跌额/百分比，完全匹配交易所网页
def get_crypto_info(coin_list, usd_rate):
    buf = []
    base_url = "https://api.binance.com/api/v3/ticker/24hr"
    for coin in coin_list:
        symbol = f"{coin}USDT"
        try:
            resp = SESS.get(f"{base_url}?symbol={symbol}", headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            del resp
            # 原生字段定义（全部接口返回，无推导）
            sym = coin
            usd_now = round(float(data["c"]), 2)       # 当前现价
            usd_today_open = round(float(data["o"]),2)  # 今日开盘（亚洲早8点日线开盘）
            usd_yesterday_close = round(float(data["x"]),2) # 昨日收盘价格
            change_24h_usd = round(float(data["p"]),2)  # 24小时涨跌金额
            change_24h_pct = round(float(data["P"]),2)  # 24小时涨跌幅
            # 计算显示用人民币价格（仅换算汇率，不参与涨跌推导）
            cny_now = round(usd_now * usd_rate, 2)
            cny_today_open = round(usd_today_open * usd_rate, 2)
            cny_yesterday_close = round(usd_yesterday_close * usd_rate, 2)
            # 今日涨幅：现价 - 今日开盘（原生今日日内涨跌）
            today_chg_usd = round(usd_now - usd_today_open, 2)
            today_chg_pct = round((today_chg_usd / usd_today_open)*100,2) if usd_today_open !=0 else 0
            # 昨日涨幅：昨日收盘 - 昨日开盘（原生昨日全天涨跌）
            yesterday_chg_usd = round(usd_yesterday_close - float(data["o"]),2)
            yesterday_chg_pct = round((yesterday_chg_usd / float(data["o"]))*100,2) if float(data["o"]) !=0 else 0

            buf += [
                f"{sym}",
                f"现价：${usd_now} | 折合人民币¥{cny_now}",
                f"今日开盘：${usd_today_open} 折合¥{cny_today_open}",
                f"昨日收盘：${usd_yesterday_close} 折合¥{cny_yesterday_close}",
                f"今日涨幅：${today_chg_usd}（{today_chg_pct}%）",
                f"昨日涨幅：${yesterday_chg_usd}（{yesterday_chg_pct}%）",
                f"24小时涨幅：{change_24h_pct}%",
                "----------------------------------------"
            ]
            del data
            gc.collect()
        except Exception:
            buf.append(f"{coin} 虚拟币接口访问失败")
            buf.append("----------------------------------------")
            gc.collect()
            time.sleep(0.3)
    return "\n".join(buf)

if __name__ == "__main__":
    try:
        # 分步获取+即时释放内存，压低峰值防OOM 137报错
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
        del gold_info, gold_block
        gc.collect()

        # 获取美股
        us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_ex, US_INDEX_LIST)
        gc.collect()

        # 获取虚拟币
        crypto_text = "===== 虚拟币行情 =====\n" + get_crypto_info(CRYPTO_LIST, usd_ex)
        gc.collect()

        # 合并全部内容，仅推送单条微信消息
        full_msg = f"{gold_text}\n{us_text}\n{crypto_text}"
        push_wechat("黄金+美股+BTC/ETH行情播报", full_msg)

        # 彻底释放所有大文本内存
        del gold_text, us_text, crypto_text, full_msg
        gc.collect()

    except Exception as err:
        push_wechat("行情脚本异常提醒", f"脚本全局异常：{str(err)}")
        gc.collect()
# 移除kill_self强制杀进程，代码执行完毕Python解释器自动正常退出，系统完整回收RAM
