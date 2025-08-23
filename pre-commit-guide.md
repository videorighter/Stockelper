# Pre-commit 설치 및 사용 가이드

이 문서는 SatCHAT 프로젝트에서 pre-commit을 설치하고 사용하는 방법을 설명합니다.

## 개요

Pre-commit은 Git 커밋 전에 자동으로 코드 검사를 실행하는 도구입니다. 이를 통해 코드 품질을 일관되게 유지하고 기본적인 오류를 방지할 수 있습니다.

## 설치 방법

### 1. pre-commit 패키지 설치

```bash
pip install pre-commit
```

### 2. Git 훅 설치

프로젝트 루트 디렉토리에서 다음 명령을 실행합니다:

```bash
pre-commit install
```

이 명령은 `.git/hooks/pre-commit` 파일을 생성하여 Git 커밋 시 자동으로 pre-commit이 실행되도록 합니다.

### 3. 훅 다운로드 및 설치

```bash
pre-commit install-hooks
```

이 명령은 `.pre-commit-config.yaml` 파일에 정의된 훅들을 다운로드하고 설치합니다.

## 현재 설정된 훅

Stockelper 프로젝트에는 다음과 같은 훅들이 설정되어 있습니다:

1. **black**: Python 코드 포맷터 (Python 3.12 버전 사용)
2. **check-yaml**: YAML 파일 유효성 검사
3. **end-of-file-fixer**: 파일 끝에 빈 줄 추가
4. **trailing-whitespace**: 줄 끝 공백 제거
5. **ruff**: Python 린터 (자동 수정 옵션 포함)

## 일상적인 사용법

### 자동 실행

Git 커밋 시 pre-commit이 자동으로 실행됩니다:

```bash
git commit -m "커밋 메시지"
```

### 수동 실행

특정 파일에 대해 수동으로 실행:

```bash
pre-commit run --files 파일경로1 파일경로2
```

모든 파일에 대해 수동으로 실행:

```bash
pre-commit run --all-files
```

특정 훅만 실행:

```bash
pre-commit run black --all-files
```

## 주의사항

1. **커밋 실패**: pre-commit 검사에 실패하면 커밋이 중단됩니다. 이는 코드 품질을 유지하기 위한 것입니다.
2. **자동 수정**: 일부 훅(black, ruff 등)은 파일을 자동으로 수정합니다. 수정 후 다시 `git add`를 해야 합니다.
3. **YAML 오류**: 다중 문서 YAML 파일은 `check-yaml` 훅에서 오류가 발생할 수 있습니다.

## 훅 업데이트

훅 버전을 최신으로 업데이트하려면:

```bash
pre-commit autoupdate
```

이 명령은 `.pre-commit-config.yaml` 파일의 `rev` 필드를 최신 버전으로 업데이트합니다.

## 훅 건너뛰기

특정 커밋에서 pre-commit을 건너뛰려면:

```bash
git commit -m "커밋 메시지" --no-verify
```

하지만 이는 긴급한 경우에만 사용하는 것이 좋습니다.

## 커스텀 훅 추가

`.pre-commit-config.yaml` 파일을 수정하여 새로운 훅을 추가할 수 있습니다. 예를 들어:

```yaml
repos:
  - repo: https://github.com/새로운/훅저장소
    rev: v1.0.0
    hooks:
      - id: 새로운-훅
```

## 결론

pre-commit은 코드 품질을 일관되게 유지하는 데 매우 유용한 도구입니다. 현재 설정된 훅들은 Python 코드 스타일과 기본적인 파일 형식을 자동으로 관리해 줍니다. 팀 프로젝트에서 모든 개발자가 동일한 코드 스타일을 유지하는 데 큰 도움이 됩니다.
