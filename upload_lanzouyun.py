import json
import os
import re
from collections import namedtuple
from datetime import datetime

from lanzou.api import LanZouCloud

from log import logger, color

Folder = namedtuple('Folder', ['name', 'id'])


# 参考文档可见：https://github.com/zaxtyson/LanZouCloud-API/wiki

class Uploader:
    folder_dnf_calc = Folder("魔改计算器", "1810329")
    folder_djc_helper = Folder("蚊子腿小助手", "2290618")
    folder_history_files = Folder("历史版本", "2303716")

    history_version_prefix = "DNF蚊子腿小助手_v"
    history_patches_prefix = "DNF蚊子腿小助手_增量更新文件_"

    regex_version = r'DNF蚊子腿小助手_v(.+)_by风之凌殇.7z'
    regex_patches = r'DNF蚊子腿小助手_增量更新文件_v(.+)_to_v(.+).7z'

    def __init__(self, cookie):
        self.lzy = LanZouCloud()
        self.login_ok = self.lzy.login_by_cookie(cookie) == LanZouCloud.SUCCESS

    def upload_to_lanzouyun(self, filepath, target_folder, history_file_prefix=""):
        logger.warning(f"开始上传 {os.path.basename(filepath)} 到 {target_folder.name}")
        run_start_time = datetime.now()

        def on_uploaded(fid, is_file):
            if not is_file:
                return

            logger.info(f"下载完成，fid={fid}")

            prefix = history_file_prefix
            if prefix == "":
                prefix = self.history_version_prefix

            files = self.lzy.get_file_list(target_folder.id)
            for file in files:
                if file.name.startswith(prefix):
                    self.lzy.move_file(file.id, self.folder_history_files.id)
                    logger.info(f"将{file.name}移动到目录({self.folder_history_files.name})")

            logger.info(f"将文件移到目录({target_folder.name})中")
            self.lzy.move_file(fid, target_folder.id)

        # 上传到指定的文件夹中
        retCode = self.lzy.upload_file(filepath, -1, callback=self.show_progress, uploaded_handler=on_uploaded)
        if retCode != LanZouCloud.SUCCESS:
            logger.error(f"上传失败，retCode={retCode}")
            return False

        logger.warning(f"上传当前文件总计耗时{datetime.now() - run_start_time}")

        return True

    def latest_version(self) -> str:
        """
        返回形如"1.0.0"的最新版本信息
        """
        latest_version_file = self.find_latest_version()
        # DNF蚊子腿小助手_v4.6.6_by风之凌殇.7z
        match = re.search(self.regex_version, latest_version_file.name)
        if match is not None:
            latest_version = match.group(1)
            return latest_version

        # 保底返回1.0.0
        return "1.0.0"

    def download_latest_version(self, download_dir) -> str:
        """
        下载最新版本压缩包到指定目录，并返回最终压缩包的完整路径
        """
        return self.download_file(self.find_latest_version(), download_dir)

    def find_latest_version(self):
        """
        查找最新版本，如找到，返回lanzouyun提供的file信息，否则抛出异常
        """
        files = self.lzy.get_file_list(self.folder_djc_helper.id)
        for file in files:
            if file.name.startswith(self.history_version_prefix):
                return file

        raise FileNotFoundError("latest version not found")

    def latest_patches_range(self):
        """
        返回形如("1.0.0", "1.1.2")的补丁范围
        """
        latest_patches_file = self.find_latest_patches()
        # DNF蚊子腿小助手_增量更新文件_v4.6.5_to_v4.6.6.7z
        match = re.search(self.regex_patches, latest_patches_file.name)
        if match is not None:
            version_left, version_right = match.group(1), match.group(2)
            return (version_left, version_right)

        # 保底返回
        return ("1.0.0", "1.0.0")

    def download_latest_patches(self, download_dir) -> str:
        """
        下载最新版本压缩包到指定目录，并返回最终压缩包的完整路径
        """
        return self.download_file(self.find_latest_patches(), download_dir)

    def find_latest_patches(self):
        """
        查找最新版本的补丁，如找到，返回lanzouyun提供的file信息，否则抛出异常
        """
        files = self.lzy.get_file_list(self.folder_djc_helper.id)
        for file in files:
            if file.name.startswith(self.history_patches_prefix):
                return file

        raise FileNotFoundError("latest patches not found")

    def download_file(self, fileinfo, download_dir) -> str:
        """
        下载最新版本压缩包到指定目录，并返回最终压缩包的完整路径
        """
        if not os.path.isdir(download_dir):
            os.mkdir(download_dir)

        download_dir = os.path.realpath(download_dir)
        target_path = os.path.join(download_dir, fileinfo.name)

        def after_downloaded(file_name):
            """下载完成后的回调函数"""
            target_path = file_name
            logger.info(f"最终下载文件路径为 {file_name}")

        logger.info(f"即将开始下载 {target_path}")
        retCode = self.lzy.down_file_by_id(fileinfo.id, download_dir, callback=self.show_progress, downloaded_handler=after_downloaded)
        if retCode != LanZouCloud.SUCCESS:
            logger.error(f"下载失败，retCode={retCode}")
            if retCode == LanZouCloud.NETWORK_ERROR:
                logger.warning(color("bold_yellow") + (
                    "蓝奏云api返回网络错误，这很可能是由于dns的问题导致的\n"
                    "分别尝试在浏览器中访问下列两个网页，是否一个打的开一个打不开？\n"
                    "https://fzls.lanzoux.com/s/djc-helper\n"
                    "https://fzls.lanzous.com/s/djc-helper\n"
                    "\n"
                    "如果是这样，请按照下面这个链接，修改本机的dns，使用阿里、腾讯、百度、谷歌dns中的任意一个应该都可以解决。\n"
                    "https://www.ypojie.com/9830.html\n"
                    "\n"
                    "如果两个都打不开，大概率是蓝奏云挂了-。-可选择忽略后面的弹框，继续运行旧版本，或者手动去QQ群或github下载最新版本"
                ))
            raise Exception("下载失败")

        return target_path

    def show_progress(self, file_name, total_size, now_size):
        """显示进度的回调函数"""
        percent = now_size / total_size
        bar_len = 40  # 进度条长总度
        bar_str = '>' * round(bar_len * percent) + '=' * round(bar_len * (1 - percent))
        show_percent = percent * 100
        now_mb = now_size / 1048576
        total_mb = total_size / 1048576
        print(f'\r{show_percent:.2f}%\t[{bar_str}] {now_mb:.1f}/{total_mb:.1f}MB | {file_name} ', end='')
        if total_size == now_size:
            print('')  # 下载完成换行


if __name__ == '__main__':
    with open("upload_cookie.json") as fp:
        cookie = json.load(fp)
    uploader = Uploader(cookie)
    if uploader.login_ok:
        # file = r"D:\_codes\Python\djc_helper_public\bandizip_portable\bz.exe"
        # uploader.upload_to_lanzouyun(file, uploader.folder_djc_helper)
        # uploader.upload_to_lanzouyun(file, uploader.folder_dnf_calc)
        # logger.info(f"最新版本为{uploader.latest_version()}")
        # uploader.download_latest_version("_update_temp_dir")

        logger.info(f"最新增量补丁范围为{uploader.latest_patches_range()}")
        # uploader.download_latest_patches("_update_temp_dir")
    else:
        logger.error("登录失败")
