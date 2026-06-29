import requests, time, gc, os, sys
from requests.adapters import HTTPAdapter, Retry

# 屏蔽全部控制台输出，输出丢黑洞，零闪存擦写
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 网络全局参数 8秒统一超时 关闭长连接 自动重试
GLOBAL_TIMEOUT = 8
SESS = requests.Session()
SESS.keep_alive = False
retry_opt = Retry(total=2, backoff_factor=0.4, status_forcelist=[429,500,502,503,504])
SESS.mount("https://", HTTPAdapter(max_retries=retry_opt))
SESS.mount("http://", HTTPAdapter(max_retries=retry_opt))

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
# 2.美股指数代码（东方财富代码：纳斯达克NDX、标普500SPX）
US_INDEX_LIST = ["NDX", "SPX"]
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

# 【已替换东方财富美股接口，彻底解决新浪403封禁】
def get_us_index(rate, idx_list):
    buf = []
    # 东方财富全球指数公开接口
    base_url = "https://push2.eastmoney.com/api/qt/globalindex/getminutekline"
    name_map = {"NDX":"纳斯达克NDX","SPX":"标普500SPX"}
    for code in idx_list:
        try:
            params = {
                "secid": f"100.{code}",
                "fields1": "f1,f2,f3,f4,f12,f13,f14,f15",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100,f101,f102,f103,f104,f105,f106,f107,f108,f109,f110,f111,f112,f113,f114,f115,f116,f117,f118,f119,f120,f121,f122,f123,f124,f125,f126,f127,f128,f129,f130,f131,f132,f133,f134,f135,f136,f137,f138,f139,f140,f141,f142,f143,f144,f145,f146,f147,f148,f149,f150,f151,f152,f153,f154,f155,f156,f157,f158,f159,f160,f161,f162,f163,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198,f199,f200,f201,f202,f203,f204,f205,f206,f207,f208,f209,f210,f211,f212,f213,f214,f215,f216,f217,f218,f219,f220,f221,f222,f223,f224,f225,f226,f227,f228,f229,f230,f231,f232,f233,f234,f235,f236,f237,f238,f239,f240,f241,f242,f243,f244,f245,f246,f247,f248,f249,f250,f251,f252,f253,f254,f255,f256,f257,f258,f259,f260,f261,f262,f263,f264,f265,f266,f267,f268,f269,f270,f271,f272,f273,f274,f275,f276,f277,f278,f279,f280,f281,f282,f283,f284,f285,f286,f287,f288,f289,f290,f291,f292,f293,f294,f295,f296,f297,f298,f299,f300,f301,f302,f303,f304,f305,f306,f307,f308,f309,f310,f311,f312,f313,f314,f315,f316,f317,f318,f319,f320,f321,f322,f323,f324,f325,f326,f327,f328,f329,f330,f331,f332,f333,f334,f335,f336,f337,f338,f339,f340,f341,f342,f343,f344,f345,f346,f347,f348,f349,f350,f351,f352,f353,f354,f355,f356,f357,f358,f359,f360,f361,f362,f363,f364,f365,f366,f367,f368,f369,f370,f371,f372,f373,f374,f375,f376,f377,f378,f379,f380,f381,f382,f383,f384,f385,f386,f387,f388,f389,f390,f391,f392,f393,f394,f395,f396,f397,f398,f399,f400,f401,f402,f403,f404,f405,f406,f407,f408,f409,f410,f411,f412,f413,f414,f415,f416,f417,f418,f419,f420,f421,f422,f423,f424,f425,f426,f427,f428,f429,f430,f431,f432,f433,f434,f435,f436,f437,f438,f439,f440,f441,f442,f443,f444,f445,f446,f447,f448,f449,f450,f451,f452,f453,f454,f455,f456,f457,f458,f459,f460,f461,f462,f463,f464,f465,f466,f467,f468,f469,f470,f471,f472,f473,f474,f475,f476,f477,f478,f479,f480,f481,f482,f483,f484,f485,f486,f487,f488,f489,f490,f491,f492,f493,f494,f495,f496,f497,f498,f499,f500",
                "lmt": "1",
                "klt": "101",
                "ut": "1780000000000",
                "_": "1780000000000"
            }
            resp = SESS.get(base_url, params=params, headers=HEADERS, timeout=GLOBAL_TIMEOUT)
            resp.raise_for_status()
            json_data = resp.json()
            del resp
            data = json_data["data"]["klines"][0].split(",")
            # 字段解析：现价、昨收、涨跌额、涨跌幅
            now = float(data[2])
            last_close = float(data[3])
            chg = float(data[4])
            chg_pct = float(data[5])
            rmb_price = round(now * rate, 2)
            buf += [
                name_map[code],
                f"点位：{now} | 折合人民币{rmb_price}",
                f"昨收：{last_close} 点",
                f"当日涨跌：{chg}点（{chg_pct}%）",
                "----------------------------------------"
            ]
            del json_data
            gc.collect()
        except Exception as e:
            buf.append(f"{name_map.get(code,code)} 指数拉取失败：{str(e)}")
            buf.append("----------------------------------------")
            gc.collect()
            time.sleep(0.3)
    gc.collect()
    return "\n".join(buf)

# 虚拟币：OKX欧易公开无密钥API，原生sodUtc8=早8点今日开盘
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
            # 原生字段读取
            sym = coin
            usd_now = round(float(data["last"]), 2)               # 当前现价
            usd_today_open = round(float(data["sodUtc8"]), 2)     # UTC8点今日开盘
            usd_24h_open = round(float(data["open24h"]), 2)       # 24h滚动开盘
            # 换算人民币
            cny_now = round(usd_now * usd_rate, 2)
            cny_today_open = round(usd_today_open * usd_rate, 2)
            # 今日涨幅：现价 - 今日8点开盘
            today_chg_usd = round(usd_now - usd_today_open, 2)
            today_chg_pct = round((today_chg_usd / usd_today_open)*100, 2) if usd_today_open != 0 else 0
            # 24小时涨幅：现价 - 24h开盘
            chg_24h_usd = round(usd_now - usd_24h_open, 2)
            chg_24h_pct = round((chg_24h_usd / usd_24h_open)*100, 2) if usd_24h_open != 0 else 0
            # 昨日涨幅：昨日全天8点开盘 → 昨日收盘（昨日收盘=今日8点开盘）
            usd_yesterday_close = usd_today_open
            usd_yesterday_open = round(2 * usd_24h_open - usd_today_open, 2)
            yesterday_chg_usd = round(usd_yesterday_close - usd_yesterday_open, 2)
            yesterday_chg_pct = round((yesterday_chg_usd / usd_yesterday_open)*100, 2) if usd_yesterday_open != 0 else 0
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

        # 获取美股（东方财富新接口，无403拦截）
        try:
            us_text = "===== 美股宽基指数 =====\n" + get_us_index(usd_ex, US_INDEX_LIST)
        except Exception as us_err:
            us_text = f"===== 美股宽基指数 =====\n美股整体获取异常：{str(us_err)}"
        gc.collect()

        # 获取虚拟币（OKX欧易接口）
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
# 无强制kill进程代码，执行完毕Python解释器自动正常退出，系统完整回收RAM
