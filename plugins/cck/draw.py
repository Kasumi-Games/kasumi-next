import random
from io import BytesIO
from PIL import Image, ImageEnhance
from nonebot.adapters.satori import MessageSegment


def image_to_message(image: Image.Image) -> MessageSegment:
    """
    将 Image 对象转换为 MessageSegment 对象

    参数:
        image (Image.Image): Image 对象

    返回:
        MessageSegment: 返回 MessageSegment 对象
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return MessageSegment.image(raw=buffer, mime="image/png")


def random_crop_image(
    image: Image.Image,
    cut_width: int,
    cut_length: int,
    is_black: int,
    cut_counts: int,
) -> MessageSegment:
    """
    根据传入的参数裁剪图像，返回处理后的 Image 对象

    参数:
        image (Image.Image): 输入图像的 Image 对象。
        cut_width (int): 裁剪的宽度。
        cut_length (int): 裁剪的长度。
        is_black (int): 图像处理模式，1 为黑白，2 为调整亮度，3 为调整对比度。
        cut_counts (int): 裁剪的次数。

    返回:
        MessageSegment: 返回处理后的图像对象。
    """
    # 初始化一个空白图像，用于拼接
    concatenated_image = Image.new(
        "RGB", (cut_width, cut_length * cut_counts), (255, 255, 255)
    )

    for i in range(cut_counts):
        # 随机计算矩形的起始坐标
        x = random.randint(0, image.width - cut_width)
        y = random.randint(0, image.height - cut_length)

        # 裁剪图片
        cropped_image = image.crop((x, y, x + cut_width, y + cut_length))

        # 将裁剪的图像粘贴到拼接图像上，留下6像素的间隔
        y_position = i * (cut_length + 6)
        concatenated_image.paste(cropped_image, (0, y_position))

    if is_black == 1:
        # 转为黑白图像
        concatenated_image = concatenated_image.convert("L")
    elif is_black == 2:
        # 调整亮度和对比度
        enhancer = ImageEnhance.Brightness(concatenated_image)
        concatenated_image = enhancer.enhance(3.7)  # 亮度
    elif is_black == 3:
        enhancer = ImageEnhance.Contrast(concatenated_image)
        concatenated_image = enhancer.enhance(0.1)  # 对比度

    original_width, original_height = concatenated_image.size
    # 计算新的宽度和高度（扩大为原来的两倍）
    new_width = original_width * 2
    new_height = original_height * 2

    # 使用新的宽度和高度进行图片尺寸调整
    doubled_image = concatenated_image.resize((new_width, new_height))

    msg = image_to_message(doubled_image)

    concatenated_image.close()

    return msg
