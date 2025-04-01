# Description: This is a demo script to show how to use the pydglab library to interact with the DGLab device.
# 描述：这是一个演示脚本，用于展示如何使用pydglab库与DGLab设备进行交互。

import asyncio  # 异步IO库，用于处理异步操作
import logging  # 日志记录库，用于输出程序运行信息
from asyncio import CancelledError  # 导入取消异常，用于处理异步操作被取消的情况

import pydglab  # 导入DGLab主库
from pydglab import model_v2  # 导入V2设备的模型定义
from pydglab.bthandler_v2 import scan  # 直接导入V2设备的扫描函数，确保只扫描V2设备

# 配置日志输出格式和级别
logging.basicConfig(
    format="%(module)s [%(levelname)s]: %(message)s", level=logging.INFO
)


async def get_user_input(prompt):
    """
    异步获取用户输入
    通过将阻塞的input()函数放入线程池执行，避免阻塞事件循环
    """
    return await asyncio.get_event_loop().run_in_executor(None, lambda: input(prompt))


async def display_menu():
    """
    显示用户交互菜单
    列出所有可用的操作选项
    """
    print("\n===== DGLAB V2控制菜单 =====")
    print("1. 设置强度 (1-100)")
    print("2. 选择波形模式")
    print("3. 获取电池电量")
    print("4. 获取当前强度")
    print("5. 关闭设备连接")
    print("========================")
    

async def display_wave_modes():
    """
    显示所有可用的波形模式
    从model_v2.Wave_set中获取所有预设波形
    """
    print("\n可用波形模式:")
    for i, wave_name in enumerate(model_v2.Wave_set):
        print(f"{i+1}. {wave_name}")


async def _():
    """
    主函数 - 处理设备扫描、连接和用户交互
    """
    dglab_instance = None  # 设备实例
    connection_initialized = False  # 连接状态标志
    keep_running = True  # 运行状态标志
    
    try:
        # 第一阶段：扫描并连接设备
        logging.info("开始扫描DGLAB V2设备...")
        # 只扫描V2设备，直接使用bthandler_v2中的scan函数
        v2_devices = await scan()
        
        # 检查是否找到设备
        if not v2_devices:
            logging.error("未找到DGLAB V2设备，请确保设备已打开并在范围内")
            return
            
        logging.info("扫描完成，准备连接...")
        
        # 获取信号最强的设备地址（按RSSI强度排序）
        device_address = sorted(v2_devices, key=lambda device: device[1])[0][0]
        logging.info(f"选择设备: {device_address}")
        
        # 创建dglab实例并传入地址
        dglab_instance = pydglab.dglab(address=device_address)
        
        try:
            # 第二阶段：初始化设备连接
            logging.info("尝试连接V2设备...")
            # create()方法会建立蓝牙连接并初始化设备
            await dglab_instance.create()
            connection_initialized = True
            logging.info("连接成功！")
            
            # 添加短暂延迟确保连接稳定
            await asyncio.sleep(0.5)
            
            # 检查是否成功连接并获取当前强度
            strength = await dglab_instance.get_strength()
            logging.info(f"当前强度: {strength}")
            
            # 设置初始参数 - 为安全起见设置最低强度
            await dglab_instance.set_strength_sync(1, 1)  # 设置初始强度为最小
            await dglab_instance.set_wave_sync(0, 0, 0, 0, 0, 0)  # 设置初始波形参数
            
            # 第三阶段：用户交互循环
            while keep_running and connection_initialized:
                # 显示菜单并获取用户选择
                await display_menu()
                choice = await get_user_input("请输入选项: ")
                
                try:
                    # 根据用户选择执行相应操作
                    if choice == "1":
                        # 选项1：设置强度
                        strength_value = await get_user_input("请输入强度 (1-100): ")
                        try:
                            strength_value = int(strength_value)
                            if 1 <= strength_value <= 100:
                                # 同时设置两个通道的强度
                                await dglab_instance.set_strength_sync(strength_value, strength_value)
                                print(f"强度设置为: {strength_value}")
                            else:
                                print("错误: 强度必须在1-100之间")
                        except ValueError:
                            print("错误: 请输入有效数字")
                            
                    elif choice == "2":
                        # 选项2：选择波形模式
                        await display_wave_modes()
                        wave_choice = await get_user_input("请选择波形模式: ")
                        try:
                            wave_idx = int(wave_choice) - 1
                            if 0 <= wave_idx < len(model_v2.Wave_set):
                                # 获取选定的波形名称并设置
                                wave_name = list(model_v2.Wave_set.keys())[wave_idx]
                                await dglab_instance.set_wave_set(model_v2.Wave_set[wave_name], model_v2.ChannelA)
                                print(f"波形模式设置为: {wave_name}")
                            else:
                                print("错误: 无效的波形选择")
                        except ValueError:
                            print("错误: 请输入有效数字")
                            
                    elif choice == "3":
                        # 选项3：获取电池电量
                        battery = await dglab_instance.get_batterylevel()
                        print(f"电池电量: {battery}%")
                        
                    elif choice == "4":
                        # 选项4：获取当前强度
                        strength = await dglab_instance.get_strength()
                        print(f"当前强度: A通道={strength[0]}, B通道={strength[1]}")
                        
                    elif choice == "5":
                        # 选项5：关闭连接
                        keep_running = False
                        print("准备关闭连接...")
                        
                    else:
                        print("无效选项，请重新选择")
                        
                except Exception as e:
                    # 捕获并处理操作过程中的异常
                    print(f"操作出错: {type(e).__name__}: {e}")
                    
                # 短暂延迟确保命令处理完成
                await asyncio.sleep(0.5)
            
        except TimeoutError:
            # 处理连接超时错误
            logging.error("连接超时，请确保设备已打开并在范围内")
        except CancelledError:
            # 处理操作被取消的情况
            logging.error("操作被取消")
        except Exception as e:
            # 处理其他异常
            logging.error(f"操作过程中出错: {type(e).__name__}: {e}")
        finally:
            # 确保在任何情况下都尝试关闭连接
            # 但仅在连接初始化成功后进行关闭
            if dglab_instance and connection_initialized:
                try:
                    logging.info("尝试关闭连接...")
                    # 检查必要的属性是否存在，避免关闭未完全初始化的连接
                    if hasattr(dglab_instance, 'wave_tasks'):
                        # 关闭连接并释放资源
                        await dglab_instance.close()
                        logging.info("连接已关闭")
                    else:
                        logging.warning("连接未完全初始化，无需关闭")
                except Exception as e:
                    logging.error(f"关闭连接时出错: {type(e).__name__}: {e}")
            elif dglab_instance:
                logging.warning("连接未成功初始化，跳过关闭操作")
    except Exception as e:
        # 捕获全局异常
        logging.error(f"全局错误: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # 程序入口点
    try:
        logging.info("程序启动...")
        # 运行主异步函数
        asyncio.run(_())
        logging.info("程序正常结束")
    except KeyboardInterrupt:
        # 处理用户中断（Ctrl+C）
        logging.info("程序被用户中断")
    except Exception as e:
        # 处理其他未捕获的异常
        logging.error(f"程序运行错误: {type(e).__name__}: {e}")