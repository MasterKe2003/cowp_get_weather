from datetime import datetime, timedelta
import re
import requests
import plugins
from plugins import *
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger

BASE_URL_ALAPI = "https://v2.alapi.cn/api/"

@plugins.register(name="get_weather",
                  desc="get_weather插件",
                  version="1.0",
                  author="masterke",
                  desire_priority=100)
class get_weather(Plugin):
    content = None
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info(f"[{__class__.__name__}] inited")

    def get_help_text(self, **kwargs):
        help_text = f""
        return help_text

    def on_handle_context(self, e_context: EventContext):
        # 只处理文本消息
        if e_context['context'].type != ContextType.TEXT:
            return
        self.content = e_context["context"].content.strip()
        weather_match = re.match(r'^(?:(.{2,7}?)(?:市|县|区|镇)?|(\d{7,9}))(?:的)?天气$', self.content)
        if weather_match:
            logger.info(f"[{__class__.__name__}] 收到消息: {self.content}")
            # 读取配置文件
            config_path = os.path.join(os.path.dirname(__file__),"config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    self.config_data = json.load(file)
            else:
                logger.error(f"请先配置{config_path}文件")
                return 
            
            reply = Reply()
            # 如果匹配成功，提取第一个捕获组
            result = self.get_weather()
            if result != None:
                reply.type = ReplyType.TEXT
                reply.content = result
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
            else:
                reply.type = ReplyType.ERROR
                reply.content = "获取失败,等待修复⌛️"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS

    def get_weather(self):
        url = BASE_URL_ALAPI + 'tianqi'
        params = f"city={self.content[:-2]}&token={self.config_data['alapi_token']}"
        try:
            resopnse = requests.get(url, params=params)
            if resopnse.status_code == 200:
                json_data = resopnse.json()
                if json_data['code'] == 200:
                    data = json_data['data']
                    update_time = data['update_time']
                    dt_object = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
                    formatted_update_time = dt_object.strftime("%m-%d %H:%M")
                    # Basic Info
                    if data['city'] not in self.content:  # 如果返回城市信息不是所查询的城市，重新输入
                        return "输入不规范，请输<国内城市+天气>，比如 '成都天气'"
                    formatted_output = []
                    basic_info = (
                        f"🏙️ 城市: {data['city']} ({data['province']})\n"
                        f"🕒 更新: {formatted_update_time}\n"
                        f"🌦️ 天气: {data['weather']}\n"
                        f"🌡️ 温度: ↓{data['min_temp']}℃| 现{data['temp']}℃| ↑{data['max_temp']}℃\n"
                        f"🌬️ 风向: {data['wind']}\n"
                        f"💦 湿度: {data['humidity']}\n"
                        f"🌅 日出/日落: {data['sunrise']} / {data['sunset']}\n"
                    )
                    formatted_output.append(basic_info)

                    # Clothing Index,处理部分县区穿衣指数返回null
                    chuangyi_data = data.get('index', {}).get('chuangyi', {})
                    if chuangyi_data:
                        chuangyi_level = chuangyi_data.get('level', '未知')
                        chuangyi_content = chuangyi_data.get('content', '未知')
                    else:
                        chuangyi_level = '未知'
                        chuangyi_content = '未知'

                    chuangyi_info = f"👚 穿衣指数: {chuangyi_level} - {chuangyi_content}\n"
                    formatted_output.append(chuangyi_info)
                    # Next 7 hours weather
                    ten_hours_later = dt_object + timedelta(hours=10)

                    future_weather = []
                    for hour_data in data['hour']:
                        forecast_time_str = hour_data['time']
                        forecast_time = datetime.strptime(forecast_time_str, "%Y-%m-%d %H:%M:%S")

                        if dt_object < forecast_time <= ten_hours_later:
                            future_weather.append(f"     {forecast_time.hour:02d}:00 - {hour_data['wea']} - {hour_data['temp']}°C")

                    future_weather_info = "⏳ 未来10小时的天气预报:\n" + "\n".join(future_weather)
                    formatted_output.append(future_weather_info)

                    # Alarm Info
                    if data.get('alarm'):
                        alarm_info = "⚠️ 预警信息:\n"
                        for alarm in data['alarm']:
                            alarm_info += (
                                f"🔴 标题: {alarm['title']}\n"
                                f"🟠 等级: {alarm['level']}\n"
                                f"🟡 类型: {alarm['type']}\n"
                                f"🟢 提示: \n{alarm['tips']}\n"
                                f"🔵 内容: \n{alarm['content']}\n\n"
                            )
                        formatted_output.append(alarm_info)

                    return "\n".join(formatted_output)
            else:
                logger.error(f"天气接口返回状态码错误:{resopnse.status_code}")
        except Exception as e:
            logger.error(f"天气接口抛出异常:{e}")
                
        logger.error("所有接口都挂了,无法获取")
        return None
