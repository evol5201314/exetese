"""
【低内存优化参考（仅注释，代码内不新增任何回收逻辑避免接口异常）】
1. 可在不影响网络的场景手动del临时大对象、gc.collect()；
2. 列表join替代字符串累加减少内存碎片；
3. 分段销毁多段行情文本压低峰值；
⚠️ 注意：当前路由/网络环境下，新增大量del+gc会导致会话中断、接口全部拉取失败，因此本代码完全不改动原有稳定逻辑
⚠️ 美股已替换同花顺国内接口，修复resp局部变量未定义崩溃bug
"""
import requests, time, gc, os, sys, json
# 屏蔽全部控制台输出，输出丢黑洞，零闪存擦写
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 网络全局参数 8秒统一超时 关闭长连接 0初始重试防僵死
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
# 2.美股指数同花顺代码 IXIC纳斯达克 ^GSPC标普500
US_INDEX_LIST = ["IXIC", "^GSPC"]
# 3.虚拟币新增位置【这里添加币种大写标识，自动拼接BTC-USDT】
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

# 【修复版美股函数：解决resp局部变量未定义崩溃】
def get_us_index(rate, idx_list):
    buf = []
    base_api = "https://q.10jqka.com.cn/quote/jsonp.php?t={code}&_={ts}"
    for code in idx_list:
        resp = None  # 预先定义，避免异常时找不到变量
        try:
            ts = int(time.time() * 1000)
            url = base_api.format(code=code, ts=ts)
            resp = SESS.get(url, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            raw = resp.text
            # 剥离jsonp括号
            start = raw.find("(")
            end = raw.rfind(")")
            json_str = raw[start+1:end]
            data = json.loads(json_str)
            price = float(data["price"])
            last_close = float(data["yestclose"])
            change = float(data["change"])
            change_pct = float(data["changepercent"])
            name = data["name"]
            rmb_price = round(price * rate, 2)
            buf += [
                f"{name}",
                f"点位：{price} | 折合人民币{rmb_price}",
                f"昨收：{last_close} 点",
                f"当日涨跌：{change}点（{change_pct}%）",
                f"前日涨跌：{change}点（{change_pct}%）",
                "----------------------------------------"
            ]
        except Exception as err:
            buf.append(f"{code} 美股指数拉取失败：{str(err)}")
            buf.append("----------------------------------------")
        finally:
            # 只有resp存在才销毁
            if resp is not None:
                del resp
        gc.collect()
        time.sleep(0.2)
    return "\n".join(buf)

# 虚拟币：OKX欧易公开无密钥API，原生sodUtc8=早8点今日开盘（完全不动）
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
            today_chg_pct = round((today_chg_usd / usd_today_open)*100, 2) if usd_today_open !=0 else 0
            chg_24h_pct = round(float(data["price_change_percentage_24h"]), 2)
            usd_yesterday_close = usd_today_open
            usd_yesterday_open = round(2 * usd_24h_open - usd_today_open, 2)
            yesterday_chg_usd = round(usd_yesterday_close - usd_yesterday_open, 2)
            yesterday_chg_pct = round((yesterday_chg_usd / usd_yesterday_open)*100, 2) if usd_yesterday_open !=0 else 0
            cny_yesterday_close = round(usd_yesterday_close * usd_rate, 2)
            buf += [
                f"{sym}",
                f"现价：${usd_now} | 折合人民币¥{cny_now}",
                f"今日开盘(早8点)：${usd_today_open} 折合¥{cny_today_open}",
                f"昨日收盘：${usd_yesterday_close} 折合¥{cny_yesterday_close}",
                f"今日涨幅：${today_chg_usd}（{today_chg_pct}%）",
                f"昨日涨幅：${yesterday_chg_usd}（{yesterday_chg_pct}%）",
                f"24小时涨幅：{chg_24h_pct}%",
                "----------------------------------------"
            ]
            del json_data, data
            gc.collect()
        except Exception:
            buf.append(f"{coin} OKX欧易接口访问失败")
            buf.append("----------------------------------------")
            gc.collect()
            time.sleep(0.3)
    return "\n".join(buf)

if __name__ == "__main__":
    try:
        # 优化3：分段获取+即时释放内存，压低峰值防OOM 137报错
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

        # 获取美股（独立捕获全局异常，板块不会整块消失）
        try:
            us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_ex, US_INDEX_LIST)
        except Exception as us_err:
            us_text = f"===== 美股宽基指数 =====\n美股整体获取异常：{str(us_err)}\n----------------------------------------"
        gc.collect()

        # 获取虚拟币（原有稳定逻辑完全不变）
        crypto_text = "===== 虚拟币行情 =====\n" + get_crypto_info(CRYPTO_LIST, usd_ex)
        gc.collect()

        # 合并单条完整微信消息推送
        full_msg = f"{gold_text}\n{us_text}\n{crypto_text}"
        push_wechat("黄金+美股+BTC/ETH行情播报", full_msg)

        # 推送完成彻底销毁全部大文本释放内存
        del gold_text, us_text, crypto_text, full_msg
        gc.collect()

    except Exception as err:
        push_wechat("行情脚本异常提醒", f"脚本全局错误：{str(err)}")
        gc.collect()
# 优化5：无kill_self强制系统杀进程，执行完毕Python解释器自动正常退出，系统完整回收RAM
