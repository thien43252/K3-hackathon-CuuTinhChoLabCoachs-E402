.PHONY: run test clean install

# Khởi chạy Discord Bot chính của dự án
run:
	uv run main.py

# Chạy toàn bộ các test cases với pytest
test:
	PYTHONPATH=. uv run pytest -v

# Cài đặt môi trường và các package cần thiết
install:
	uv sync

# Dọn dẹp cache và các file rác sinh ra trong quá trình chạy
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf cloned_repos/
