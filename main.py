"""
# 新增低内存优化注释（仅优化内存，不改动原有可正常运行的网络逻辑）
优化1：删除全局无用变量、临时对象每次del+gc.collect()，及时释放大json/响应体
优化2：字符串拼接统一用列表join，减少内存碎片，替代频繁字符串+拼接
优化3：循环内临时浮点/列表用完立刻销毁，不长期驻留内存
优化4：移除无意义临时中间变量，精简栈内存占用
优化5：每段行情生成完成后立即销毁上游数据源对象，不同时多段大文本驻留RAM
优化6：仅保留必要字段解析，不缓存完整接口返回原始数据
优化7：无新增网络逻辑、不改UA/keep_alive/请求间隔，保证OKX、新浪接口正常访问
优化8：所有gc回收逻辑行内标注，后续修改不会误删内存释放代码
"""
import requests, time, gc, os, sys
# 屏蔽全部控制台输出，输出丢黑洞，零闪存擦写
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 网络全局参数 8秒统一超时 关闭长连接 0初始重试防僵死（原版稳定逻辑保留不动）
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
    gc.collect() # 优化1：推送完立刻回收临时请求对象

# 黄金+美元汇率获取逻辑不变，增加及时销毁大对象优化
def get_gold_data():
    for api in API_LIST:
        try:
            resp = SESS.get(api, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            del resp # 优化1：销毁网络响应大对象
            res = {}
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
            del data # 优化1：销毁完整json数据源，不占用内存
            gc.collect()
            return res
        except Exception:
            time.sleep(0.5)
            gc.collect()
    raise Exception("全部金价接口请求超时/失败")

# A股解析函数完整保留，启用只需解开主程序两行注释，优化字符串拼接
def get_stock_info(code_list):
    code_param = [] # 优化2：列表拼接替代字符串累加，减少内存碎片
    for code in code_list:
        if code.startswith("6"):
            code_param.append(f"sh{code}")
        else:
            code_param.append(f"sz{code}")
    code_param = ",".join(code_param)
    url = f"http://hq.sinajs.cn/list={code_param}"
    buf = []
    try:
        r = SESS.get(url, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
        raw_text = r.text
        del r # 优化1：销毁响应对象
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
            buf.extend([
                f"【{stock_code} {name}】",
                f"现价：{now_price} 元",
                f"昨收：{last_close} 元",
                f"当日涨跌：{change} 元（{change_pct}%）",
                "----------------------------------------"
            ])
        del raw_text # 优化1：销毁完整返回文本
    except Exception as e:
        buf.append(f"股票接口整体请求失败：{e}")
    gc.collect()
    return "\n".join(buf)

# 美股指数函数：增强容错，保证不会整块丢失，增加内存回收
def get_us_index(rate, idx_list):
    buf = []
    url = f"http://hq.sinajs.cn/list={','.join(idx_list)}"
    try:
        resp = SESS.get(url, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
        text_lines = resp.text.split(";")
        del resp # 优化1：销毁响应对象
        if not "".join(text_lines).strip():
            buf.append("新浪美股接口被运营商IP拦截，无代理无法获取")
            buf.append("----------------------------------------")
            return "\n".join(buf)
        for line in text_lines:
            line = line.strip()
            if not line or '="' not in line:
                continue
            field_arr = line.split('"')[1].split(",")
            if len(field_arr) < 4:
                buf.extend(["指数数据残缺，跳过", "----------------------------------------"])
                continue
            try:
                idx_name = field_arr[0]
                now = float(field_arr[1])
                chg = float(field_arr[2])
                chg_pct = float(field_arr[3])
                yest_pt = float(field_arr[4]) if len(field_arr)>=5 else float(field_arr[1])
            except Exception:
                buf.extend([f"{field_arr[0]}数值解析失败", "----------------------------------------"])
                continue
            last_close = round(now - chg, 2)
            day_chg = round(last_close - yest_pt, 2)
            day_pct = round((day_chg / yest_pt)*100, 2) if yest_pt != 0 else 0
            rmb_price = round(now * rate, 2)
            buf.extend([
                idx_name,
                f"点位：{now} | 折合人民币{rmb_price}",
                f"昨收：{last_close} 点",
                f"当日涨跌：{chg}点（{chg_pct}%）",
                f"前日涨跌：{day_chg}点（{day_pct}%）",
                "----------------------------------------"
            ])
        del text_lines # 优化1：销毁原始文本列表
        if len(buf) == 0:
            buf.append("未读取到任何美股指数行情")
    except Exception as err:
        buf.append(f"美股指数拉取失败：{str(err)}")
        buf.append("----------------------------------------")
    gc.collect()
    return "\n".join(buf)

# 虚拟币OKX原版逻辑完全不动，仅增加临时对象及时销毁优化
def get_crypto_info(coin_list, usd_rate):
    buf = []
    base_url = "https://www.okx.com/api/v5/market/ticker"
    for coin in coin_list:
        inst_id = f"{coin}-USDT"
        try:
            resp = SESS.get(f"{base_url}?instId={inst_id}", headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            json_data = resp.json()
            del resp # 优化1：销毁网络响应
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
            buf.extend([
                f"{sym}",
                f"现价：${usd_now} | 折合人民币¥{cny_now}",
                f"今日开盘(早8点)：${usd_today_open} 折合¥{cny_today_open}",
                f"昨日收盘：${usd_yesterday_close} 折合¥{cny_yesterday_close}",
                f"今日涨幅：${today_chg_usd}（{today_chg_pct}%）",
                f"昨日涨幅：${yesterday_chg_usd}（{yesterday_chg_pct}%）",
                f"24小时涨幅：{chg_24h_pct}%",
                "----------------------------------------"
            ])
            del json_data, data # 优化1：销毁完整json原始数据，不驻留内存
            gc.collect()
        except Exception:
            buf.append(f"{coin} OKX欧易接口访问失败")
            buf.append("----------------------------------------")
            gc.collect()
            time.sleep(0.3)
    return "\n".join(buf)

if __name__ == "__main__":
    try:
        # 优化5：分段获取+分段销毁上游数据源，内存不同时存放多段大文本
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
        del gold_info, gold_block # 优化1：销毁黄金原始数据和列表
        gc.collect()

        # 获取美股，独立捕获异常保证变量存在不会空白板块
        try:
            us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_ex, US_INDEX_LIST)
        except Exception as us_err:
            us_text = f"===== 美股宽基指数 =====\n美股整体获取异常：{str(us_err)}"
        gc.collect() # 优化5：释放黄金内存，仅留存美股文本

        # 获取虚拟币
        crypto_text = "===== 虚拟币行情 =====\n" + get_crypto_info(CRYPTO_LIST, usd_ex)
        gc.collect() # 优化5：释放美股内存，仅留存虚拟币文本

        # 合并单条推送
        full_msg = f"{gold_text}\n{us_text}\n{crypto_text}"
        push_wechat("黄金+美股+BTC/ETH行情播报", full_msg)

        # 推送完成彻底销毁所有大文本，释放全部内存
        del gold_text, us_text, crypto_text, full_msg
        gc.collect()
    except Exception as err:
        push_wechat("行情脚本异常提醒", f"脚本全局异常：{str(err)}")
        gc.collect()
# 无强制kill进程代码，执行完毕Python解释器自动正常退出，系统完整回收RAM
