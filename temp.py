import os

# 체크: 이 폴더에 출력 가능한 항목이 있는지 확인
def has_valid_files(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(('.jsx', '.html', '.css', '.py', '.c', '.cpp', '.h')):
                return True
    return False

# 트리 출력
def print_filtered_tree(path, prefix=''):
    entries = sorted([
        f for f in os.listdir(path)
        if not f.startswith('.') and (
            os.path.isdir(os.path.join(path, f)) or f.endswith(('.jsx', '.html', '.css', '.py', '.c', '.cpp', '.h'))
        )
    ])

    # 유효한 항목만 필터링 (비어있는 폴더 제외)
    filtered_entries = []
    for f in entries:
        if f == os.path.basename(__file__):  # 자기 자신 제외
            continue
        full_path = os.path.join(path, f)
        if os.path.isdir(full_path):
            if has_valid_files(full_path):
                filtered_entries.append(f)
        else:
            filtered_entries.append(f)

    for i, entry in enumerate(filtered_entries):
        full_path = os.path.join(path, entry)
        is_last = (i == len(filtered_entries) - 1)
        branch = '└── ' if is_last else '├── '
        print(prefix + branch + entry)

        if os.path.isdir(full_path):
            extension = '    ' if is_last else '│   '
            print_filtered_tree(full_path, prefix + extension)

# 사용 예시
print("Smart-Feature/")
print_filtered_tree("C:\YS\TUK\Capstone\Smart IV pole\github_clone\Smart-Feature")
