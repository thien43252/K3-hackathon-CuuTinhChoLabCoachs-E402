import os
import subprocess
import shutil

def clone_repo(repo_url: str, dest_dir: str, branch: str = None) -> str:
    """
    Tải (Clone) một Git repository về thư mục dest_dir để chuẩn bị tài liệu cho Agent.
    Nếu thư mục đích đã tồn tại, sẽ thực hiện cập nhật (git pull).
    
    Args:
        repo_url (str): Đường dẫn git clone (HTTPS hoặc SSH).
        dest_dir (str): Đường dẫn thư mục lưu trữ cục bộ.
        branch (str, optional): Nhánh cụ thể cần clone.
        
    Returns:
        str: Đường dẫn tuyệt đối tới thư mục chứa repo đã clone/cập nhật.
    """
    try:
        # Chuyển dest_dir thành đường dẫn tuyệt đối
        dest_path = os.path.abspath(dest_dir)
        
        # Nếu thư mục .git đã tồn tại -> Chỉ cần git pull để cập nhật tài liệu mới nhất
        if os.path.exists(os.path.join(dest_path, ".git")):
            print(f"🔄 Thư mục đã tồn tại. Đang cập nhật repository tại: {dest_path}...")
            # Chạy git pull
            result = subprocess.run(
                ["git", "-C", dest_path, "pull"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ Cập nhật thành công: {result.stdout.strip()}")
            return dest_path
            
        # Nếu thư mục đã tồn tại nhưng không phải git repo -> Xóa đi để clone lại sạch sẽ
        if os.path.exists(dest_path):
            print(f"⚠️ Thư mục tồn tại nhưng không phải Git repo. Đang dọn dẹp...")
            shutil.rmtree(dest_path)
            
        # Chuẩn bị lệnh clone
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        command = ["git", "clone"]
        if branch:
            command.extend(["-b", branch])
        command.extend([repo_url, dest_path])
        
        print(f"🚀 Đang clone repo {repo_url} về {dest_path}...")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ Clone thành công!")
        return dest_path

    except subprocess.CalledProcessError as e:
        error_msg = f"❌ Lỗi Git Command: {e.stderr.strip()}"
        print(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"❌ Lỗi không xác định khi clone repo: {str(e)}"
        print(error_msg)
        raise RuntimeError(error_msg) from e
