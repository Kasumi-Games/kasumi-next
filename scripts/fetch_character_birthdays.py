import json
import httpx
from datetime import datetime

# 定义要请求的 URL 模板
url_template = "https://bestdori.com/api/characters/{}.json"

# 定义一个空字典来保存数据
character_birthdays = {}

# 遍历 i 从 1 到 40
for i in range(1, 41):
    try:
        # 向指定 URL 发送请求
        response = httpx.get(url_template.format(i))

        # 确保请求成功
        if response.status_code == 200:
            # 将 JSON 响应解析为字典
            character_data = response.json()

            # 获取 characterName 和 birthday
            character_name = character_data["characterName"][0]
            birthday = character_data["profile"]["birthday"]

            # 确保 characterName 和 birthday 存在
            if character_name and birthday:
                # 解析 birthday 字段

                # 转换为秒
                timestamp_s = int(birthday) / 1000

                # 将其转换为日期时间对象
                date_time = datetime.utcfromtimestamp(timestamp_s + 24 * 3600)
                formatted_birthday = date_time.strftime("%m月%d日")

                # 将数据保存到字典中
                character_birthdays[character_name] = formatted_birthday
        else:
            print(
                f"请求 URL 失败: {url_template.format(i)}，状态码: {response.status_code}"
            )

    except Exception as e:
        print(f"处理 URL {url_template.format(i)} 时发生错误: {str(e)}")

# 将字典保存为 JSON 文件
with open("character_birthdays.json", "w", encoding="utf-8") as json_file:
    json.dump(character_birthdays, json_file, ensure_ascii=False, indent=4)

print("已将数据保存到 character_birthdays.json 文件中。")
