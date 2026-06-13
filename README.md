# Timeline to Lightroom

Google Timeline JSON에서 지정 기간의 위치 경로를 추출하여 Adobe Lightroom
Classic에서 불러올 수 있는 GPX 트랙로그와 선택적 KML 파일로 변환하는 Windows
애플리케이션입니다.

모든 Timeline 경로 처리는 PC 안에서 수행됩니다. 온라인 지도를 사용할 때는 현재
지도 영역에 해당하는 타일 요청만 OpenStreetMap 서버로 전송되며 Timeline 경로
데이터 자체는 전송되지 않습니다.

## 주요 기능

- 최신 Android/iOS 기기 Timeline 내보내기의 `semanticSegments` 자동 인식
- Google Takeout `Records.json` 및 월별 Semantic Location History 자동 인식
- 국가별 IANA 시간대와 시작·종료 일시 필터
- Lightroom Classic용 GPX 1.1과 선택적 KML `gx:Track` 생성
- 마우스 이동·확대/축소가 가능한 세계 지도 경로 미리보기
- 마우스 휠클릭 또는 `전체 경로 맞춤` 버튼으로 경로 전체 보기
- 온라인 OpenStreetMap과 연결 실패 시 내장 오프라인 세계 지도
- 한국어/영어 UI

## 사용 방법

1. Google Maps에서 Timeline 데이터를 JSON으로 내보냅니다.
2. 앱에서 JSON 파일 또는 JSON 파일들이 들어 있는 폴더를 선택합니다.
3. 국가·시간대와 시작·종료 일시를 지정하고 지도에서 경로를 확인합니다.
4. 출력 폴더와 KML 추가 생성 여부를 선택한 뒤 `GPX 변환`을 누릅니다.
5. Lightroom Classic에서 `Map > Tracklog > Load Tracklog`로 GPX 파일을 불러옵니다.
6. 필요한 사진을 선택하고 `Map > Tracklog > Auto-Tag Selected Photos`를 사용합니다.

Lightroom Classic은 GPX 트랙로그만 직접 불러옵니다. 카메라 시간이 실제 현지
시간과 다르면 Lightroom Classic의 `Set Tracklog Time Offset` 기능을 사용하십시오.

참고 문서:

- [Adobe Lightroom Classic Map module](https://helpx.adobe.com/lightroom-classic/help/maps-module.html)
- [Google Maps Timeline on Android](https://support.google.com/maps/answer/6258979?co=GENIE.Platform%3DAndroid&hl=en)
- [Google Maps Timeline on iOS](https://support.google.com/maps/answer/6258979?co=GENIE.Platform%3DiOS&hl=en)
- [Google KML reference](https://developers.google.com/kml/documentation/kmlreference)

## 지원 입력

- 기기 내보내기 JSON: 루트에 `semanticSegments`가 있는 파일
- Takeout 원시 기록: 루트에 `locations`가 있는 `Records.json`
- Takeout Semantic Location History: 루트에 `timelineObjects`가 있는 월별 JSON

폴더를 선택하면 하위 폴더의 JSON 파일도 검색하며 지원되는 파일만 합칩니다.
Google의 비공개 JSON 구조가 변경되면 일부 항목이 제외될 수 있습니다.

## 개발 및 실행

Python 3.11 이상이 필요합니다.

```powershell
python -m pip install -e ".[dev]"
python -m timeline_to_lightroom
python -m pytest -q
```

Windows portable 앱 빌드:

```powershell
python -m PyInstaller TimelineToLightroom.spec --noconfirm
```

Inno Setup 6이 설치되어 있으면 `installer/TimelineToLightroom.iss`로 설치
프로그램을 만들 수 있습니다.

## 라이선스

프로젝트 코드는 MIT License입니다. 포함된 지도 자산의 라이선스와 출처는
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)를 참조하십시오.
