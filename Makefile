.PHONY: test clean

test:
	pytest tests/

clean:
	rm *.png || rm *.bin || rm -rf .pytest_cache __pycache__
