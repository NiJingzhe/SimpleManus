#!/usr/bin/env python3
"""
使用Adafruit_DHT库实现的DHT11传感器读取工具
依赖Adafruit_DHT库，适用于树莓派平台
"""

import time
import json
from datetime import datetime
from SimpleLLMFunc import tool

try:
    import Adafruit_DHT
    ADAFRUIT_DHT_AVAILABLE = True
except ImportError:
    ADAFRUIT_DHT_AVAILABLE = False
    #print("⚠️ Adafruit_DHT库未安装，请使用以下命令安装:")
    #print("pip install Adafruit_DHT")
    #print("或者: sudo apt-get install python3-dev python3-pip")
    #print("      sudo python3 -m pip install --upgrade setuptools")
    #print("      git clone https://github.com/adafruit/Adafruit_Python_DHT.git")
    #print("      cd Adafruit_Python_DHT")
    #print("      sudo python3 setup.py install")

@tool(
    name="read_dht11_adafruit",
    description="使用Adafruit_DHT库读取DHT11传感器温度和湿度数据，适用于树莓派平台。直接调用即可返回当前温湿度值。",
)
def read_dht11_adafruit() -> str:
    """
    使用Adafruit_DHT库读取DHT11传感器数据
    
    无需参数，直接调用即返回当前温度和湿度
    
    Returns:
        str: 包含温度和湿度数据的JSON字符串
    """
    
    #print("🌡️ 开始使用Adafruit_DHT库读取DHT11传感器...")
    
    # 检查Adafruit_DHT库是否可用
    if not ADAFRUIT_DHT_AVAILABLE:
        result = {
            "success": False,
            "error": "Adafruit_DHT库未安装或不可用",
            "sensor_info": {
                "type": "DHT11",
                "method": "Adafruit_DHT",
                "library_status": "missing"
            },
            "timestamp": datetime.now().isoformat(),
            "installation_guide": [
                "pip install Adafruit_DHT",
                "sudo apt-get install python3-dev python3-pip",
                "git clone https://github.com/adafruit/Adafruit_Python_DHT.git",
                "cd Adafruit_Python_DHT && sudo python3 setup.py install",
                "确保在树莓派上运行"
            ]
        }
        #print("❌ Adafruit_DHT库未安装")
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    # 默认使用GPIO 4引脚 (可以根据需要修改为26等其他引脚)
    gpio_pin = 4
    max_retries = 5
    
    temperature = None
    humidity = None
    last_error = None
    
    # 多次尝试读取
    for attempt in range(max_retries):
        #print(f"📡 尝试读取 {attempt + 1}/{max_retries}...")
        
        try:
            # 使用Adafruit_DHT.read_retry读取DHT11传感器
            # 参数: 11表示DHT11传感器类型，gpio_pin是GPIO引脚号
            humidity, temperature = Adafruit_DHT.read_retry(11, gpio_pin)
            
            if temperature is not None and humidity is not None:
                #print(f"✅ 读取成功: 温度 {temperature:.1f}°C, 湿度 {humidity:.1f}%")
                break
            else:
                last_error = "传感器返回空值，可能是连接问题或读取超时"
                #print(f"❌ 尝试 {attempt + 1} 失败: {last_error}")
                
                # 等待一段时间再重试
                if attempt < max_retries - 1:
                    time.sleep(2)
                    
        except Exception as e:
            last_error = f"异常: {str(e)}"
            #print(f"❌ 尝试 {attempt + 1} 异常: {last_error}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    # 构建返回结果
    current_time = datetime.now()
    
    if temperature is not None and humidity is not None:
        result = {
            "temperature": {
                "value": round(temperature, 1),
                "unit": "°C"
            },
            "humidity": {
                "value": round(humidity, 1),
                "unit": "%"
            },
            "readable_time": current_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    else:
        result = {
            "success": False,
            "error": last_error or "未知错误",
            "sensor_info": {
                "type": "DHT11", 
                "gpio_pin": gpio_pin,
                "method": "Adafruit_DHT",
                "total_attempts": max_retries
            },
            "timestamp": current_time.isoformat(),
            "suggestions": [
                "检查DHT11传感器连接是否正确",
                "确认GPIO引脚连接到DHT11的DATA引脚",
                "检查电源连接(3.3V或5V)",
                "确保运行在树莓派上并有GPIO访问权限",
                "可以尝试更换GPIO引脚",
                "确保传感器工作正常"
            ]
        }
    
    return json.dumps(result, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # 直接测试
    #print("🧪 测试Adafruit_DHT DHT11传感器读取...")
    result = read_dht11_adafruit()
    #print("\n📋 完整结果:")
    #print(result)
