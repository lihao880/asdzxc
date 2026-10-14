
import os
import json
import sys

def scan_and_generate_json(target_dir=None, output_filename="tvbox_py.json"):
    """
    使用QPython运行，扫描指定目录下的所有.py文件，并生成TVBox可用的JSON配置文件。‌
    
    Args:
        target_dir (str): 要扫描的目录路径，默认为当前脚本所在目录。
        output_filename (str): 输出的JSON文件名。
    """
    # 如果未指定目录，则使用当前脚本所在的目录
    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 确保目录存在
    if not os.path.exists(target_dir):
        print(f"错误: 目录 '{target_dir}' 不存在。")
        return

    # 获取目录下所有的 .py 文件
    py_files = []
    try:
        for file in os.listdir(target_dir):
            if file.endswith(".py") and file != os.path.basename(__file__):
                # 排除当前脚本本身，避免将自己也加入配置
                py_files.append(file)
    except Exception as e:
        print(f"读取目录时出错: {e}")
        return

    # 排序文件列表，保证输出顺序一致（可选）
    py_files.sort()

    if not py_files:
        print(f"在目录 '{target_dir}' 中未找到任何 .py 文件。")
        return

    # 构建 sites 列表
    sites = []
    for py_file in py_files:
        # 提取文件名作为 name，去掉 .py 后缀
        name_without_ext = os.path.splitext(py_file)[0]
        
        site_entry = {
            "key": f"{name_without_ext}py",
            "name": name_without_ext,
            "type": 3,
            "api": f"./{py_file}"
        }
        sites.append(site_entry)

    # 构建最终 JSON 结构
    config_data = {
        "sites": sites
    }

    # 确定输出文件的完整路径
    output_path = os.path.join(target_dir, output_filename)

    # 写入 JSON 文件
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # ensure_ascii=False 保证中文正常显示
            # indent=4 使JSON格式化易读
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        print(f"成功生成配置文件: {output_path}")
        print(f"共扫描到 {len(sites)} 个 Python 源文件。")
    except Exception as e:
        print(f"写入文件时出错: {e}")

if __name__ == "__main__":
    # 可以通过命令行参数指定目录，例如: python scan_tvbox.py /path/to/pyfiles
    if len(sys.argv) > 1:
        target_directory = sys.argv[1]
    else:
        target_directory = None
    
    scan_and_generate_json(target_dir=target_directory)
