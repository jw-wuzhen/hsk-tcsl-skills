#!/usr/bin/env python3
"""从zuowen.com抓取真实范文 - 供平台智能体通过bash调用"""
import sys
import re
import html
import urllib.request

TOPIC_URLS = {
    # === 热点话题 ===
    "旅行": "https://www.zuowen.com/redianhuti/lvxingzw/",
    "旅游": "https://www.zuowen.com/redianhuti/lvyouzw/",
    "环境": "https://www.zuowen.com/redianhuti/huanjingzw/",
    "保护环境": "https://www.zuowen.com/redianhuti/huanjingzw/",
    "朋友": "https://www.zuowen.com/redianhuti/pengyouzw/",
    "友情": "https://www.zuowen.com/redianhuti/pengyouzw/",
    "童年": "https://www.zuowen.com/redianhuti/tongnianzw/",
    "童年趣事": "https://www.zuowen.com/redianhuti/tongnianzw/",
    "读书": "https://www.zuowen.com/redianhuti/dushuzw/",
    "阅读": "https://www.zuowen.com/redianhuti/yueduzw/",
    "我和书": "https://www.zuowen.com/redianhuti/whszw/",
    "书的故事": "https://www.zuowen.com/redianhuti/whszw/",
    "成长": "https://www.zuowen.com/redianhuti/chengzhangzw/",
    "感恩": "https://www.zuowen.com/redianhuti/ganenzw/",
    "感恩老师": "https://www.zuowen.com/redianhuti/gelszw/",
    "感恩父母": "https://www.zuowen.com/redianhuti/gefmzw/",
    "理想": "https://www.zuowen.com/redianhuti/lixiangzw/",
    "梦想": "https://www.zuowen.com/redianhuti/mengxiangzw/",
    "母亲": "https://www.zuowen.com/redianhuti/muaizw/",
    "妈妈": "https://www.zuowen.com/redianhuti/mm/",
    "成功": "https://www.zuowen.com/redianhuti/chenggongzw/",
    "坚持": "https://www.zuowen.com/redianhuti/jianchizw/",
    "校园": "https://www.zuowen.com/redianhuti/xiaoyuanzw/",
    "校园生活": "https://www.zuowen.com/redianhuti/xyshzw/",
    "课余生活": "https://www.zuowen.com/redianhuti/kysh/",
    "自我介绍": "https://www.zuowen.com/redianhuti/zwjs/",
    "我学会了": "https://www.zuowen.com/redianhuti/xuehui/",
    "祖国": "https://www.zuowen.com/redianhuti/zuguo/",
    "爱国": "https://www.zuowen.com/redianhuti/aiguozw/",
    "交通安全": "https://www.zuowen.com/redianhuti/jtaqzw/",
    # === 情感类 ===
    "同情": "https://www.zuowen.com/redianhuti/tongqingzw/",
    "苦难": "https://www.zuowen.com/redianhuti/kunnanzw/",
    "记忆": "https://www.zuowen.com/redianhuti/jiyizw/",
    "关爱": "https://www.zuowen.com/redianhuti/guanaizw/",
    "烦恼": "https://www.zuowen.com/redianhuti/fannaozw/",
    "尊严": "https://www.zuowen.com/redianhuti/zunyanzw/",
    "愧疚": "https://www.zuowen.com/redianhuti/kuijiuzw/",
    "感谢": "https://www.zuowen.com/redianhuti/ganxiezw/",
    "谎言": "https://www.zuowen.com/redianhuti/huangyanzw/",
    "孝": "https://www.zuowen.com/redianhuti/xiaozw/",
    "误会": "https://www.zuowen.com/redianhuti/wuhuizw/",
    "完美": "https://www.zuowen.com/redianhuti/wanmeizw/",
    "痛苦": "https://www.zuowen.com/redianhuti/tongkuzw/",
    "真情": "https://www.zuowen.com/redianhuti/zhenqingzw/",
    "亲情": "https://www.zuowen.com/redianhuti/qinqingzw/",
    "渴望": "https://www.zuowen.com/redianhuti/kewangzw/",
    "敬佩": "https://www.zuowen.com/redianhuti/jingpeizw/",
    "期盼": "https://www.zuowen.com/redianhuti/qipanzw/",
    "期待": "https://www.zuowen.com/redianhuti/qidaizw/",
    # === 励志类 ===
    "独立": "https://www.zuowen.com/redianhuti/dulizw/",
    "奉献": "https://www.zuowen.com/redianhuti/fengxianzw/",
    "美德": "https://www.zuowen.com/redianhuti/meidezw/",
    "珍惜": "https://www.zuowen.com/redianhuti/zhenxizw/",
    "珍惜时间": "https://www.zuowen.com/redianhuti/zxsjzw/",
    "珍爱生命": "https://www.zuowen.com/redianhuti/zasmzw/",
    "细节": "https://www.zuowen.com/redianhuti/xijiezw/",
    "责任": "https://www.zuowen.com/redianhuti/zerenzw/",
    "微笑": "https://www.zuowen.com/redianhuti/weixiaozw/",
    "幸福": "https://www.zuowen.com/redianhuti/xingfuzw/",
    "生命": "https://www.zuowen.com/redianhuti/shengmingzw/",
    "道德": "https://www.zuowen.com/redianhuti/daodezw/",
    "机会": "https://www.zuowen.com/redianhuti/jhzw/",
    "态度": "https://www.zuowen.com/redianhuti/taiduzw/",
    "启示": "https://www.zuowen.com/redianhuti/qishizw/",
    "努力": "https://www.zuowen.com/redianhuti/nulizw/",
    "目标": "https://www.zuowen.com/redianhuti/mubiaozw/",
    "命运": "https://www.zuowen.com/redianhuti/mingyuzw/",
    "奋斗": "https://www.zuowen.com/redianhuti/fendouzw/",
    "成熟": "https://www.zuowen.com/redianhuti/chengshuzw/",
    "希望": "https://www.zuowen.com/redianhuti/xiwangzw/",
    "挫折": "https://www.zuowen.com/redianhuti/cuozhezw/",
    "自信": "https://www.zuowen.com/redianhuti/zixinzw/",
    "信心": "https://www.zuowen.com/redianhuti/xinxinzw/",
    "包容": "https://www.zuowen.com/redianhuti/baorongzw/",
    "宽容": "https://www.zuowen.com/redianhuti/kuanrongzw/",
    "放弃": "https://www.zuowen.com/redianhuti/fangqizw/",
    "心愿": "https://www.zuowen.com/redianhuti/xinyuanzw/",
    "忍耐": "https://www.zuowen.com/redianhuti/rennaizw/",
    "苦恼": "https://www.zuowen.com/redianhuti/kunaozw/",
    "和谐": "https://www.zuowen.com/redianhuti/hexiezw/",
    "团结": "https://www.zuowen.com/redianhuti/tuanjiezw/",
    "勤奋": "https://www.zuowen.com/redianhuti/qinfenzw/",
    "改变": "https://www.zuowen.com/redianhuti/gaibianzw/",
    "勇气": "https://www.zuowen.com/redianhuti/yongqizw/",
    "诚信": "https://www.zuowen.com/redianhuti/chengxinzw/",
    "信任": "https://www.zuowen.com/redianhuti/xinrezw/",
    "信念": "https://www.zuowen.com/redianhuti/xnzw/",
    "追求": "https://www.zuowen.com/redianhuti/zqzw/",
    "反思": "https://www.zuowen.com/redianhuti/fszw/",
    "尊重": "https://www.zuowen.com/redianhuti/zzzw/",
    "尝试": "https://www.zuowen.com/redianhuti/changshizw/",
    "心灵美": "https://www.zuowen.com/redianhuti/xlmzw/",
    "长大": "https://www.zuowen.com/redianhuti/wzdzw/",
    "收获": "https://www.zuowen.com/redianhuti/shouhuozw/",
    "修养": "https://www.zuowen.com/redianhuti/xiuyangzw/",
    "思考": "https://www.zuowen.com/redianhuti/sikaozw/",
    "生存": "https://www.zuowen.com/redianhuti/shengcunzw/",
    # === 人物类 ===
    "老师": "https://www.zuowen.com/redianhuti/laoshizw/",
    "同学": "https://www.zuowen.com/redianhuti/tongxuezw/",
    "父爱": "https://www.zuowen.com/redianhuti/fuaizw/",
    "爸爸": "https://www.zuowen.com/redianhuti/bb/",
    "父母": "https://www.zuowen.com/redianhuti/fumuzw/",
    "父母的爱": "https://www.zuowen.com/redianhuti/fmdazw/",
    "爷爷": "https://www.zuowen.com/redianhuti/yy/",
    "奶奶": "https://www.zuowen.com/redianhuti/nainaizw/",
    "外公": "https://www.zuowen.com/redianhuti/wg/",
    "外婆": "https://www.zuowen.com/redianhuti/wp/",
    "哥哥": "https://www.zuowen.com/redianhuti/gegezw/",
    "姐姐": "https://www.zuowen.com/redianhuti/jiejiezw/",
    "弟弟": "https://www.zuowen.com/redianhuti/didizw/",
    "妹妹": "https://www.zuowen.com/redianhuti/meimeizw/",
    "偶像": "https://www.zuowen.com/redianhuti/ouxiangzw/",
    "自己": "https://www.zuowen.com/redianhuti/zijizw/",
    "对手": "https://www.zuowen.com/redianhuti/duishouzw/",
    "亲人": "https://www.zuowen.com/redianhuti/qinrenzw/",
    "叔叔": "https://www.zuowen.com/redianhuti/shushuzw/",
    "母爱": "https://www.zuowen.com/redianhuti/muaizw/",
    "雷锋": "https://www.zuowen.com/redianhuti/leifengzw/",
    # === 事件类 ===
    "运动会": "https://www.zuowen.com/redianhuti/yundonghuizw/",
    "寒假": "https://www.zuowen.com/redianhuti/hanjiazw/",
    "放假": "https://www.zuowen.com/redianhuti/fangjiazw/",
    "毕业": "https://www.zuowen.com/redianhuti/biyezw/",
    "考试": "https://www.zuowen.com/redianhuti/kaoshizw/",
    "初中生活": "https://www.zuowen.com/redianhuti/chuzhongshenghuozw/",
    "探险": "https://www.zuowen.com/redianhuti/tanxianzw/",
    "健身": "https://www.zuowen.com/redianhuti/jianshen/",
    "运动": "https://www.zuowen.com/redianhuti/yundongzw/",
    "劳动": "https://www.zuowen.com/redianhuti/laodongzw/",
    "经历": "https://www.zuowen.com/redianhuti/jinglizw/",
    "竞争": "https://www.zuowen.com/redianhuti/jingzhengzw/",
    "军训": "https://www.zuowen.com/redianhuti/junxunzw/",
    # === 节日类 ===
    "春节": "https://www.zuowen.com/redianhuti/chunjiezw/",
    "新年": "https://www.zuowen.com/redianhuti/xinnianzw/",
    "过年": "https://www.zuowen.com/redianhuti/guonianzw/",
    "除夕": "https://www.zuowen.com/redianhuti/chuxi/",
    "元旦": "https://www.zuowen.com/redianhuti/yuandanzw/",
    "元宵节": "https://www.zuowen.com/redianhuti/yuanxiaojiezw/",
    "清明节": "https://www.zuowen.com/redianhuti/qmj/",
    "劳动节": "https://www.zuowen.com/redianhuti/laodongjiezw/",
    "儿童节": "https://www.zuowen.com/redianhuti/ertongjiezw/",
    "端午节": "https://www.zuowen.com/redianhuti/duanwuzw/",
    "教师节": "https://www.zuowen.com/redianhuti/jiaoshijiezw/",
    "中秋节": "https://www.zuowen.com/redianhuti/zhongqiujiezw/",
    "国庆节": "https://www.zuowen.com/redianhuti/guoqingzw/",
    "重阳节": "https://www.zuowen.com/redianhuti/chongyangjiezw/",
    "圣诞节": "https://www.zuowen.com/redianhuti/shengdiangjiezw/",
    "生日": "https://www.zuowen.com/redianhuti/srzw/",
    "节日": "https://www.zuowen.com/redianhuti/jierizw/",
    "父亲节": "https://www.zuowen.com/redianhuti/fqjzw/",
    "妇女节": "https://www.zuowen.com/redianhuti/fnj/",
    "植树节": "https://www.zuowen.com/redianhuti/zsj/",
    # === 自然类 ===
    "季节": "https://www.zuowen.com/redianhuti/sijizw/",
    "四季": "https://www.zuowen.com/redianhuti/sijizw/",
    "春天": "https://www.zuowen.com/redianhuti/chuntian/",
    "夏天": "https://www.zuowen.com/redianhuti/xiatianzw/",
    "秋天": "https://www.zuowen.com/redianhuti/qiutianzw/",
    "冬天": "https://www.zuowen.com/redianhuti/dongtianzw/",
    "雨": "https://www.zuowen.com/redianhuti/chunyuzw/",
    "春雨": "https://www.zuowen.com/redianhuti/cyzw/",
    "雪": "https://www.zuowen.com/redianhuti/xuezw/",
    "雾": "https://www.zuowen.com/redianhuti/wuzw/",
    "风": "https://www.zuowen.com/redianhuti/fengzw/",
    "月亮": "https://www.zuowen.com/redianhuti/yueliangzw/",
    "水": "https://www.zuowen.com/redianhuti/shuizw/",
    "大海": "https://www.zuowen.com/redianhuti/dahaizw/",
    "黄河": "https://www.zuowen.com/redianhuti/huanghezw/",
    "山": "https://www.zuowen.com/redianhuti/shanzw/",
    "风景": "https://www.zuowen.com/redianhuti/fengjingzw/",
    "景色": "https://www.zuowen.com/redianhuti/jingsezw/",
    "自然": "https://www.zuowen.com/redianhuti/ziranzw/",
    "大自然": "https://www.zuowen.com/redianhuti/ziranzw/",
    "植物": "https://www.zuowen.com/redianhuti/zhiwuzw/",
    "花": "https://www.zuowen.com/redianhuti/huazw/",
    "荷花": "https://www.zuowen.com/redianhuti/hehuazw/",
    "梅花": "https://www.zuowen.com/redianhuti/meihuazw/",
    "菊花": "https://www.zuowen.com/redianhuti/qiujuzw/",
    "桂花": "https://www.zuowen.com/redianhuti/ghzw/",
    "树": "https://www.zuowen.com/redianhuti/shumuzw/",
    "枫树": "https://www.zuowen.com/redianhuti/fengshuzw/",
    "叶子": "https://www.zuowen.com/redianhuti/yezizw/",
    "日落": "https://www.zuowen.com/redianhuti/riluozw/",
    "夜空": "https://www.zuowen.com/redianhuti/yekongzw/",
    "秋风": "https://www.zuowen.com/redianhuti/qiufengzw/",
    "秋雨": "https://www.zuowen.com/redianhuti/qiuyuzw/",
    # === 动物类 ===
    "猫": "https://www.zuowen.com/redianhuti/maozw/",
    "狗": "https://www.zuowen.com/redianhuti/gouzw/",
    "马": "https://www.zuowen.com/redianhuti/mazw/",
    "鸟": "https://www.zuowen.com/redianhuti/niaozw/",
    "熊猫": "https://www.zuowen.com/redianhuti/xiongmaozw/",
    "蝴蝶": "https://www.zuowen.com/redianhuti/hudiezw/",
    # === 话题类 ===
    "网络": "https://www.zuowen.com/redianhuti/wangluozw/",
    "科技": "https://www.zuowen.com/redianhuti/kejizw/",
    "游戏": "https://www.zuowen.com/redianhuti/youxizw/",
    "音乐": "https://www.zuowen.com/redianhuti/yinyuezw/",
    "艺术": "https://www.zuowen.com/redianhuti/yishuzw/",
    "规则": "https://www.zuowen.com/redianhuti/guizezw/",
    "安全": "https://www.zuowen.com/redianhuti/anquanzw/",
    "习惯": "https://www.zuowen.com/redianhuti/xiguanzw/",
    "路": "https://www.zuowen.com/redianhuti/luzw/",
    "桥": "https://www.zuowen.com/redianhuti/qiaozw/",
    "书": "https://www.zuowen.com/redianhuti/shuzw/",
    "观察": "https://www.zuowen.com/redianhuti/guanchazw/",
    "发现": "https://www.zuowen.com/redianhuti/faxianzw/",
    "我的发现": "https://www.zuowen.com/redianhuti/wdfx/",
    "声音": "https://www.zuowen.com/redianhuti/shengyinzw/",
    "世界": "https://www.zuowen.com/redianhuti/shijiezw/",
    "舞台": "https://www.zuowen.com/redianhuti/wutaizw/",
    "长城": "https://www.zuowen.com/redianhuti/changchengzw/",
    "故宫": "https://www.zuowen.com/redianhuti/gugongzw/",
    "课堂": "https://www.zuowen.com/redianhuti/ketangzw/",
    "剪纸": "https://www.zuowen.com/redianhuti/jianzhizw/",
    "漫画": "https://www.zuowen.com/redianhuti/manhuazw/",
    "哲理": "https://www.zuowen.com/redianhuti/zhelizw/",
    "假如": "https://www.zuowen.com/redianhuti/jiaruzw/",
    "人生": "https://www.zuowen.com/redianhuti/renshengzw/",
    "学习": "https://www.zuowen.com/redianhuti/xuexizw/",
    "快乐": "https://www.zuowen.com/redianhuti/kuailezw/",
    "感动": "https://www.zuowen.com/redianhuti/gandongzw/",
    "分享": "https://www.zuowen.com/redianhuti/fenxiangzw/",
    "帮助": "https://www.zuowen.com/redianhuti/bangzhuzw/",
    "时间": "https://www.zuowen.com/redianhuti/shijianzw/",
    "家庭": "https://www.zuowen.com/redianhuti/jiatingzw/",
    "家乡": "https://www.zuowen.com/redianhuti/guxiangzw/",
    "故乡": "https://www.zuowen.com/redianhuti/guxiangzw/",
    "母校": "https://www.zuowen.com/redianhuti/muxiaozw/",
    "和平": "https://www.zuowen.com/redianhuti/hpzw/",
    "低碳生活": "https://www.zuowen.com/redianhuti/dtshzw/",
    "保护树木": "https://www.zuowen.com/redianhuti/bhsmzw/",
    "爱护眼睛": "https://www.zuowen.com/redianhuti/yanjingzw/",
    "一封信": "https://www.zuowen.com/redianhuti/yfxzw/",
    "演讲稿": "https://www.zuowen.com/redianhuti/yjg/",
    "电影观后感": "https://www.zuowen.com/redianhuti/hsdianying/",
    "人口": "https://www.zuowen.com/redianhuti/renkouzw/",
}

HSK_WORD_RANGE = {
    "1": (50, 150),
    "2": (100, 200),
    "3": (150, 300),
    "4": (300, 500),
    "5": (500, 750),
    "6": (600, 900),
}

# 文言文高频词，用来跳过文言文作文
CLASSICAL_MARKERS = ["予至", "乃返", "盖", "矣", "曰", "戊戌", "腊月", "予亦", "遂", "复见", "复向前", "不可胜记", "楹联", "予心", "与之", "亦有", "皆"]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    raw = resp.read()
    # Try gb18030 first (zuowen.com uses gb18030), fallback to utf-8
    try:
        return raw.decode("gb18030")
    except (UnicodeDecodeError, ValueError):
        try:
            return raw.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            return raw.decode("gb18030", errors="replace")


def is_classical(text):
    """检测是否为文言文"""
    count = sum(1 for m in CLASSICAL_MARKERS if m in text)
    return count >= 3


def get_essay_links(topic_url):
    """从话题页提取作文链接和标题"""
    html_text = fetch(topic_url)
    pattern = r'href="(https://www\.zuowen\.com/e/\d+/[a-f0-9]+\.shtml)"[^>]*>([^<]+)'
    matches = re.findall(pattern, html_text)
    seen = set()
    result = []
    for url, title in matches:
        if url not in seen:
            seen.add(url)
            result.append((url, title.strip()))
    return result


def extract_word_count(title):
    """从标题提取字数"""
    m = re.search(r'(\d+)\s*字', title)
    return int(m.group(1)) if m else 0


def get_essay_content(essay_url):
    """从作文详情页提取正文"""
    html_text = fetch(essay_url)
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html_text, re.S)
    essay_parts = []
    for p in paragraphs:
        clean = re.sub(r'<[^>]+>', '', p)
        clean = html.unescape(clean).strip()
        # 跳过页脚、脚本、广告
        if not clean or len(clean) < 5:
            continue
        skip_words = ["作文网", "document", "script", "关于我们", "营销合作", "友情链接",
                       "网站地图", "服务协议", "投稿须知", "问题反馈", "联系我们",
                       "京ICP", "公安局", "举报电话", "举报邮箱", "中学生写作",
                       "微信公众号", "var ", "src="]
        if any(w in clean for w in skip_words):
            continue
        # 正文段落通常包含 &nbsp; 或以全角空格开头或较长
        if '&nbsp;' in p or clean.startswith('\u3000') or len(clean) > 15:
            clean = clean.replace('\u3000', '').replace('\xa0', '').strip()
            if clean and len(clean) > 5:
                essay_parts.append(clean)
    return '\n\n'.join(essay_parts)


def print_result(title, wc, url, hsk, content):
    print("=" * 50)
    print(f"标题: {title}")
    print(f"字数: 约{wc}字")
    print(f"来源: {url}")
    print(f"推荐HSK等级: {hsk}")
    print("=" * 50)
    print()
    print(content)


def main():
    if len(sys.argv) < 3:
        print("用法: python fetch_essay.py [话题] [HSK等级]")
        print("话题: 旅行,环境,朋友,童年,读书,成长,感恩,理想,母亲,成功,校园,季节,网络")
        print("等级: 1-6")
        sys.exit(1)

    topic = sys.argv[1]
    hsk = sys.argv[2]

    topic_url = None
    for key, url in TOPIC_URLS.items():
        if key in topic:
            topic_url = url
            break

    if not topic_url:
        print(f"ERROR: 不支持的话题'{topic}'")
        print(f"支持的话题: {', '.join(set(TOPIC_URLS.keys()))}")
        sys.exit(1)

    min_words, max_words = HSK_WORD_RANGE.get(hsk, (300, 800))

    print(f"正在从zuowen.com抓取【{topic}】话题的作文(HSK{hsk}, {min_words}-{max_words}字)...")
    print(f"话题页: {topic_url}")
    print()

    links = get_essay_links(topic_url)
    if not links:
        print("ERROR: 未能从话题页提取到作文链接")
        sys.exit(1)

    # 按字数筛选（标题中包含字数的）
    candidates = []
    no_wc_links = []
    for url, title in links:
        wc = extract_word_count(title)
        if wc > 0 and min_words <= wc <= max_words:
            candidates.append((url, title, wc))
        elif wc == 0:
            no_wc_links.append((url, title))

    # 如果有字数标注的候选，优先使用
    if candidates:
        for url, title, wc in candidates:
            content = get_essay_content(url)
            if not content or len(content) < 50:
                continue
            if is_classical(content):
                continue
            print_result(title, wc, url, hsk, content)
            sys.exit(0)

    # 没有字数标注的候选，尝试抓取前5篇看实际长度
    tried = 0
    for url, title in no_wc_links[:5]:
        content = get_essay_content(url)
        if not content or len(content) < 50:
            continue
        if is_classical(content):
            continue
        actual_len = len(content.replace('\n', '').replace(' ', ''))
        if min_words <= actual_len <= max_words:
            print_result(title, actual_len, url, hsk, content)
            sys.exit(0)
        tried += 1

    # 都不匹配，放宽范围，取第一篇可用的
    for url, title in no_wc_links[:5]:
        content = get_essay_content(url)
        if not content or len(content) < 50:
            continue
        if is_classical(content):
            continue
        actual_len = len(content.replace('\n', '').replace(' ', ''))
        print_result(title, actual_len, url, hsk, content)
        sys.exit(0)

    print("ERROR: 未能找到合适的作文")


if __name__ == "__main__":
    main()
