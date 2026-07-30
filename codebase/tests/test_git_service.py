import os
import pytest
from app.services.git_service import clone_repo

# GitHub test repository (siêu nhỏ, lý tưởng cho việc chạy test nhanh)
TEST_REPO_URL = "https://github.com/octocat/Spoon-Knife.git"

def test_clone_repo_new(tmp_path):
    """
    Test trường hợp clone một repository hoàn toàn mới về thư mục trống.
    """
    dest_dir = tmp_path / "spoon_knife"
    dest_str = str(dest_dir)

    # Thực hiện clone
    cloned_path = clone_repo(repo_url=TEST_REPO_URL, dest_dir=dest_str)

    # Kiểm tra đường dẫn trả về chính xác
    assert cloned_path == os.path.abspath(dest_str)
    
    # Kiểm tra thư mục đích đã được tạo
    assert os.path.exists(dest_str)
    
    # Kiểm tra có sự tồn tại của thư mục cấu hình git
    assert os.path.exists(os.path.join(dest_str, ".git"))


def test_clone_repo_update(tmp_path):
    """
    Test trường hợp thư mục đã tồn tại và đã là git repo (sẽ chạy git pull để update).
    """
    dest_dir = tmp_path / "spoon_knife"
    dest_str = str(dest_dir)

    # Chạy lần 1 để clone mới về
    clone_repo(repo_url=TEST_REPO_URL, dest_dir=dest_str)

    # Chạy lần 2 trên cùng thư mục để kiểm tra tính năng cập nhật (git pull)
    cloned_path_updated = clone_repo(repo_url=TEST_REPO_URL, dest_dir=dest_str)

    # Kiểm tra vẫn cập nhật chính xác và không báo lỗi
    assert cloned_path_updated == os.path.abspath(dest_str)
    assert os.path.exists(os.path.join(dest_str, ".git"))


def test_clone_repo_non_git_exists(tmp_path):
    """
    Test trường hợp thư mục đích đã tồn tại nhưng KHÔNG PHẢI là một git repo.
    Hệ thống cần tự động xóa đi và thực hiện clone mới sạch sẽ.
    """
    dest_dir = tmp_path / "spoon_knife"
    dest_str = str(dest_dir)

    # Tạo trước thư mục giả lập không phải git và ghi file nháp vào đó
    os.makedirs(dest_str, exist_ok=True)
    dummy_file = os.path.join(dest_str, "dummy.txt")
    with open(dummy_file, "w") as f:
        f.write("This is a non-git folder.")

    # Tiến hành gọi hàm clone
    cloned_path = clone_repo(repo_url=TEST_REPO_URL, dest_dir=dest_str)

    # Kiểm tra đường dẫn và thư mục .git mới
    assert cloned_path == os.path.abspath(dest_str)
    assert os.path.exists(os.path.join(dest_str, ".git"))
    
    # Đảm bảo file dummy.txt cũ đã bị xóa sạch trong quá trình dọn dẹp
    assert not os.path.exists(dummy_file)
