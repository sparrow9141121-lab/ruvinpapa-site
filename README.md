# 빈이아빠 홈페이지

유튜브 채널 [빈이아빠에게 물어봐](https://www.youtube.com/@ChronosArche_ruvinpapa)와
블로그 [ruvinfather.com](https://ruvinfather.com) 의 내용을 모아 보여주는 한 장짜리 홈페이지입니다.

## 파일

| 파일 | 하는 일 |
|---|---|
| `index.html` | 홈페이지 본체 |
| `update-content.py` | 유튜브·블로그를 읽어 `index.html` 의 `<!-- AUTO:... -->` 구역을 채우는 스크립트 |
| `update-content.bat` | 위 스크립트를 윈도우에서 더블클릭으로 실행 |
| `.github/workflows/update-content.yml` | GitHub 에서 매일 아침 8시(한국시간) 자동 실행 |

## 갱신되는 내용

- 주제 카드의 **대표 영상** — 역사 / 과학 / 경제별 조회수 1위 영상
- 경제 카드의 **대표 글** — 블로그 최신 글
- **최근 올라온 이야기** — 유튜브 최신 영상 3개, 블로그 최신 글 3개
- 히어로 카드의 세 줄 요약, 마지막 갱신 시각

### 깃허브에서 돌 때의 예외

유튜브가 깃허브 서버 쪽 접속에는 조회수를 내주지 않는 경우가 있습니다.
그때는 **대표 영상을 지금 올라가 있는 것 그대로 두고** 최신 목록과 대표 글만 갱신합니다.
(대표 영상 순위를 새로 매기려면 내 컴퓨터에서 한 번 실행해 주세요.)

대표를 직접 고르고 싶으면 `update-content.py` 위쪽의 `PIN`(영상 ID)과
`PIN_POST`(글 주소)에 값을 적으면 자동 선정보다 우선합니다.

## 내 컴퓨터에서 갱신하기

바탕화면의 **홈페이지 콘텐츠 갱신** 바로가기를 더블클릭하거나,
이 폴더에서 다음을 실행합니다.

```
python update-content.py
```

갱신 직전 파일은 `index.bak.html` 로 남습니다.

## GitHub Pages 로 올리기 (한 번만 하면 됩니다)

1. GitHub 에서 저장소를 새로 만듭니다. (Public)
2. 이 폴더를 그 저장소에 올립니다.

   ```
   git init
   git add .
   git commit -m "홈페이지 첫 커밋"
   git branch -M main
   git remote add origin https://github.com/<아이디>/<저장소이름>.git
   git push -u origin main
   ```

3. 저장소 **Settings → Pages** 에서 Source 를 `Deploy from a branch`,
   Branch 를 `main` / `/ (root)` 로 지정하고 저장합니다.
4. 몇 분 뒤 `https://<아이디>.github.io/<저장소이름>/` 에서 홈페이지가 열립니다.
5. 저장소 **Settings → Actions → General** 의 *Workflow permissions* 를
   **Read and write permissions** 로 바꿔 둡니다. (자동 갱신 결과를 커밋하는 데 필요)

이후에는 매일 아침 8시에 워크플로가 돌면서 새 영상·새 글을 반영하고,
바뀐 내용이 있을 때만 커밋합니다. **Actions** 탭의 *콘텐츠 자동 갱신* 에서
`Run workflow` 를 눌러 즉시 돌려볼 수도 있습니다.
