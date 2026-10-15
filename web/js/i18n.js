// Interface language (story text itself stays as the data has it). The Japanese string is the key;
// t() returns it unchanged in Japanese, or the English / Chinese entry. {name} placeholders are filled
// from `vars`. The choice is per browser (localStorage), defaulting to the browser's language.

export const LANGS = { ja: '日本語', en: 'English', zh: '中文' };

function detect() {
  try { const s = localStorage.getItem('dm.lang'); if (LANGS[s]) return s; } catch {}
  const n = (navigator.language || '').toLowerCase();
  return n.startsWith('ja') ? 'ja' : n.startsWith('zh') ? 'zh' : 'en';
}
export let lang = detect();
export function setLang(l) {
  if (!LANGS[l]) return;
  lang = l;
  try { localStorage.setItem('dm.lang', l); } catch {}
  document.documentElement.lang = l === 'zh' ? 'zh-Hant' : l;
}
document.documentElement.lang = lang === 'zh' ? 'zh-Hant' : lang;

// [en, zh]
const D = {
  // header / home
  'ダンメモ アーカイブ': ['DanMemo Archive', 'ダンメモ 劇情典藏'],
  'ダンまち〜メモリア・フレーゼ〜 アーカイブ': ['DanMachi: Memoria Freese Archive', 'ダンまち〜メモリア・フレーゼ〜 劇情典藏'],
  'シナリオ {n} 本 ・ 既読 {r}': ['{n} scenarios · {r} read', '劇情 {n} 段 ・ 已讀 {r}'],
  'ストーリー': ['Story', '劇情'],
  'アルバム': ['Album', '相簿'],
  'その他': ['Others', '其他'],
  'カード': ['Cards', '卡片'],
  'キャラストーリー': ['Character Stories', '角色劇情'],
  '立ち絵': ['Portraits', '角色立繪'],
  'セットアップ': ['Setup', '建置設定'],
  'キャラストーリー →': ['Character Stories →', '角色劇情 →'],
  '立ち絵 →': ['Portraits →', '角色立繪 →'],
  'その他のシナリオ': ['Other Scenarios', '其他劇情'],
  'エンドクレジット': ['End Credits', '片尾名單'],
  'ムービー': ['Movies', '影片'],
  'その他のイベント': ['Other Events', '其他活動'],
  '復刻イベント': ['Reruns', '復刻活動'],
  '内容が初回と異なる復刻イベント（新しい順）。': ['Reruns whose content differs from the first run (newest first).', '內容和首次舉辦不同的復刻活動（由新到舊）。'],
  'メモリアルアプリのアルバムに収録されていない、開催期間のあるイベント（新しい順）。': ["Events with a run period that the memorial app's album leaves out (newest first).", '紀念版相簿沒有收錄、但有開催期間的活動（由新到舊）。'],
  '予告・拠点ノベル': ['Previews & home-screen stories', '預告・據點劇情'],
  '拠点ノベル・予告': ['Home-screen stories & previews', '據點劇情・預告'],
  '日付順': ['by date', '依日期'],
  'アニメ{n}期 放映前ノベル': ['TV anime season {n}: pre-broadcast stories', '動畫第 {n} 期 播出前劇情'],
  'TVアニメの各話放送前に起動時に流れたノベル（日付順）。': ['Stories the game played at start-up before each TV-anime episode aired, by date.', '動畫每集播出前，遊戲啟動時播放的劇情（依日期）。'],
  '起動時に期間限定で流れたノベルのうち、特定のイベントに属さないもの（日付順）。': ['Stories the game played at start-up for a limited time that belong to no single event, by date.', '遊戲啟動時限期播放、不屬於特定活動的劇情（依日期）。'],
  'バレンタイン企画': ['Valentine event', '情人節企劃'],
  'バレンタイン': ['Valentine', '情人節'],
  'ボイス {n}': ['Voices {n}', '語音 {n}'],
  'キャラクターごとの衣装エピソード・キャラクエスト・ふれあい・ボイス。': ['Costume episodes, character quests, interaction stories and voice lines per character.', '每個角色的服裝劇情、角色任務、互動劇情與語音。'],
  'プロフィール': ['Profile', '角色介紹'],
  '{n}歳': ['age {n}', '{n} 歲'],
  '再生': ['Play', '播放'],
  '音声なし': ['No audio', '無語音'],
  '（テキストなし）': ['(no text)', '（無文字）'],
  'ログイン': ['Login', '登入'],
  '交流ページ': ['Communication page', '交流頁'],
  '挨拶': ['Greetings', '問候'],
  'タッチ': ['Touch', '觸摸'],
  '交流': ['Talk', '交流'],
  '放置': ['Idle', '放置'],
  '街': ['Town', '城鎮'],
  'アラーム': ['Alarm', '鬧鐘'],
  '衣装チェンジ': ['Costume change', '換裝'],
  'システム': ['System', '系統'],
  'ベル向け': ['to Bell', '對貝爾'],
  'アイズ向け': ['to Ais', '對艾絲'],
  'レフィーヤ向け': ['to Lefiya', '對蕾菲亞'],
  '頭': ['Head', '頭'],
  '体': ['Body', '身體'],
  '朝': ['Morning', '早'],
  '昼': ['Day', '午'],
  '夕': ['Evening', '傍晚'],
  '夜': ['Night', '晚'],
  'タイトルコール': ['Title call', '標題語音'],
  'ステータス': ['Status', '狀態'],
  'フレンド': ['Friend', '好友'],
  'プレゼント': ['Present', '禮物'],
  '6周年ムービー': ['6th Anniversary Movies', '6 周年影片'],
  '登場するお話': ['Appears in', '出處劇情'],
  'ホーム': ['Home', '首頁'],
  '言語': ['Language', '語言'],
  '見つかりません': ['Not found', '找不到'],
  '✕ 閉じる': ['✕ Close', '✕ 關閉'],
  '閉じる': ['Close', '關閉'],
  '読み込みに失敗しました：{e}': ['Failed to load: {e}', '讀取失敗：{e}'],
  '先に {cmd} を実行して web/data を作成してください。': ['Run {cmd} first to create web/data.', '請先執行 {cmd} 產生 web/data。'],
  // story
  '{a} 冒険 ・ {e} 話': ['{a} adventures · {e} episodes', '{a} 個冒險 ・ {e} 話'],
  ' ・ アルバム {n}': [' · Album {n}', ' ・ 相簿 {n}'],
  '{e} 話': ['{e} episodes', '{e} 話'],
  '{r}/{n} 既読': ['{r}/{n} read', '{r}/{n} 已讀'],
  'タイトルで検索…': ['Search titles…', '搜尋標題…'],
  'アルバム収録：': ['In the album:', '收錄於相簿：'],
  '復刻あり': ['Rerun merged', '含復刻'],
  '同じ内容の復刻をまとめました': ['Reruns with the same content are merged into this entry', '已合併內容相同的復刻'],
  '▶ この話を再生': ['▶ Play episode', '▶ 播放本話'],
  '既読': ['Read', '已讀'],
  // album
  '周年ストーリー': ['Anniversary Stories', '周年故事'],
  'イベントストーリー': ['Event Stories', '活動故事'],
  'このデータにはアルバムがありません。': ['This data has no album.', '這份資料沒有相簿。'],
  '▶ 最初から再生': ['▶ Play from the start', '▶ 從頭播放'],
  'ストーリー連続再生': ['Continuous playback', '連續播放'],
  // by character
  'キャラクターごとの衣装エピソード・キャラクエスト・ふれあい。': ['Costume episodes, character quests and interactions for each character.', '每個角色的服裝劇情、角色任務與交流。'],
  'キャラ名で検索…': ['Search characters…', '搜尋角色…'],
  '衣装 {n}': ['Costumes {n}', '服裝 {n}'],
  'キャラクエ': ['Character Quests', '角色任務'],
  'キャラクエスト': ['Character Quests', '角色任務'],
  'ふれあい': ['Interactions', '交流'],
  '▶ 再生': ['▶ Play', '▶ 播放'],
  '衣装エピソード': ['Costume Episodes', '服裝劇情'],
  '{n} 種類の表情': ['{n} expressions', '{n} 種表情'],
  // others
  'ストーリー一覧に含まれないシナリオ（キー名で分類）。': ['Scenarios that are not in the story index, grouped by key name.', '不在劇情目錄裡的劇情，依檔名分組。'],
  '絞り込み…': ['Filter…', '篩選…'],
  '{n} 本': ['{n} scenarios', '{n} 段'],
  // assets no source has (player notice and list marker)
  'このシナリオの素材の一部は、現存するどのデータにも含まれていないため表示されません：{list}': ['Some of this scenario\'s assets survive in none of the available data and are not shown: {list}', '此劇情有部分素材在現存的任何資料中都找不到，無法顯示：{list}'],
  '素材欠落：{list}': ['Missing assets: {list}', '缺少素材：{list}'],
  '画像 {n}': ['{n} image(s)', '圖片 {n}'],
  '動画 {n}': ['{n} movie(s)', '影片 {n}'],
  '立ち絵 {n}': ['{n} portrait(s)', '立繪 {n}'],
  'エフェクト {n}': ['{n} effect(s)', '特效 {n}'],
  'ボイス {n}': ['{n} voice line(s)', '語音 {n}'],
  'BGM・効果音 {n}': ['{n} music/sound(s)', '音樂・音效 {n}'],
  '次回予告': ['Next-episode previews', '下回預告'],
  'ふれあい反応 1': ['Interaction reactions 1', '交流反應 1'],
  'ふれあい反応 2': ['Interaction reactions 2', '交流反應 2'],
  'ふれあい反応 3': ['Interaction reactions 3', '交流反應 3'],
  'メイン（未分類）': ['Main (unsorted)', '主線（未分類）'],
  // story categories (adventure field 2; names come from build_web.py)
  'メイン': ['Main Story', '主線'],
  '衣装': ['Costumes', '服裝'],
  '曜日イベント': ['Daily Events', '每日活動'],
  '経験値クエスト': ['EXP Quests', '經驗值任務'],
  'ヴァリスクエスト': ['Valis Quests', '法利任務'],
  '降臨イベント': ['Descent Events', '降臨活動'],
  'ストーリーイベント': ['Story Events', '劇情活動'],
  'チュートリアル': ['Tutorial', '教學'],
  'エイナの学習クエスト': ["Eina's Study Quests", '艾伊娜的學習任務'],
  '怪物祭': ['Monsterphilia', '怪物祭'],
  '迷宮踏破': ['Dungeon Delve', '迷宮踏破'],
  '復帰応援クエスト': ['Comeback Quests', '回歸應援任務'],
  '栄光挑戦': ['Glory Challenge', '榮光挑戰'],
  'マップイベント': ['Map Events', '地圖活動'],
  'レイドイベント': ['Raid Events', '討伐活動'],
  '武器素材クエスト': ['Weapon Material Quests', '武器素材任務'],
  'ファミリア共闘': ['Familia Co-op Battles', '眷族共鬥'],
  '派閥闘劇': ['Familia Showdown', '派閥鬥劇'],
  '冒険者レベル': ['Adventurer Level', '冒險者等級'],
  '派閥殲滅戦': ['Familia Annihilation Battle', '派閥殲滅戰'],
  'デイリーリセットクエスト': ['Daily Reset Quests', '每日重置任務'],
  '英雄昇華チュートリアル': ['Sublimation Tutorial', '英雄昇華教學'],
  'ウィークリークエスト': ['Weekly Quests', '每週任務'],
  '七闘領域': ['Seven Battle Domains', '七鬥領域'],
  '決戦試練': ['Decisive Trials', '決戰試煉'],
  '派閥大戦': ['Familia War', '派閥大戰'],
  // player
  '← 目録': ['← Index', '← 目錄'],
  'ボイス': ['Voice', '語音'],
  '非表示': ['Hide', '隱藏'],
  '全画面': ['Full screen', '全螢幕'],
  '画面を常にオン': ['Keep screen on', '螢幕常亮'],
  '再生中': ['While playing', '播放劇情時'],
  '常に': ['Always', '一律'],
  'しない': ['Off', '關閉'],
  'テキストボックスを隠す（スクリーンショット用・H／右クリック）': ['Hide the text box for screenshots (H / right-click)', '隱藏對話框以便截圖（H／右鍵）'],
  '設定': ['Settings', '設定'],
  '色': ['Colour', '顏色'],
  '不透明度': ['Opacity', '不透明度'],
  'SKIP 間隔': ['Skip delay', 'SKIP 間隔'],
  '秒': ['s', '秒'],
  'デフォルト': ['Default', '預設'],
  '次へ：{t}': ['Next: {t}', '下一段：{t}'],
  '最後のシナリオです': ['This is the last scenario', '這是最後一段'],
  '主字幕': ['Subtitles', '主字幕'],
  'テキストボックスの高さ': ['Text box height', '對話框高度'],
  'セリフに合わせる': ['Fit each line', '隨內容'],
  '一定': ['Fixed', '固定'],
  '副字幕': ['Second subtitles', '副字幕'],
  '日本語': ['Japanese', '日文'],
  '中文': ['Chinese', '中文'],
  'このシナリオには{l}の字幕がありません': ['No {l} subtitles in this story', '這段劇情沒有{l}字幕'],
  '一部のセリフには{l}の字幕がありません': ['Some lines have no {l} subtitles', '部分台詞沒有{l}字幕'],
  'もう一度': ['Replay', '再看一次'],
  '目録へ': ['Back to index', '回到目錄'],
  // galleries
  'ドラッグで幅を調整': ['Drag to resize', '拖曳調整寬度'],
  'カード|image': ['Card', '卡面'],
  '全身': ['Full body', '全身'],
  'ガチャ': ['Gacha', '抽卡'],
  'バストアップ': ['Bust', '半身'],
  '消費MP {n}': ['MP {n}', '消耗MP {n}'],
  'アシストスキル': ['Assist Skill', '輔助技能'],
  '必殺技': ['Special Arts', '必殺技'],
  '技': ['Skills', '技能'],
  'なし': ['None', '無'],
  '{e}属性': ['{e} element', '{e}屬性'],
  '英雄祭': ['Hero Festival', '英雄祭'],
  '期間限定': ['Limited', '期間限定'],
  '冒険者': ['Adventurer', '冒險者'],
  'アシスト': ['Assist', '輔助'],
  '▶ ガチャ演出': ['▶ Gacha reveal', '▶ 抽卡演出'],
  'ステイタス': ['Status', '能力值'],
  '熟練度 {a}/{b}': ['Mastery {a}/{b}', '熟練度 {a}/{b}'],
  '英雄昇華': ['Sublimation', '英雄昇華'],
  '限界突破': ['Limit Break', '極限突破'],
  '物攻': ['P.Atk', '物攻'],
  '魔攻': ['M.Atk', '魔攻'],
  '防御': ['Def', '防禦'],
  '最大ランク・熟練度最大の値です（記念アプリの「キャラ詳細」と同じ計算）。': ["Values at max rank and max mastery (same calculation as the memorial app's character details).", '最大階級、熟練度全滿時的數值（與紀念 App「角色詳細」相同的計算）。'],
  'スキル/発展アビリティ': ['Skills / Development Abilities', '技能／發展能力'],
  '衣装ストーリー': ['Costume Story', '服裝劇情'],
  'クリック / Space で進む ・ Esc で閉じる': ['Click / Space to continue · Esc to close', '點擊／空白鍵繼續 ・ Esc 關閉'],
  'すべて': ['All', '全部'],
  '全レア': ['All rarities', '全稀有度'],
  '全属性': ['All elements', '全屬性'],
  '通常': ['Standard', '一般'],
  '衣装ストーリーあり': ['Has costume story', '有服裝劇情'],
  '全キャラ': ['All characters', '全角色'],
  '称号・名前で検索…': ['Search title or name…', '搜尋稱號・名字…'],
  '{n} 枚': ['{n} cards', '{n} 張'],
  '祭': ['Fes', '祭'],
  // card type (build_web.py TYPE)
  '物理攻撃型': ['Physical Attacker', '物理攻擊型'],
  '魔法攻撃型': ['Magic Attacker', '魔法攻擊型'],
  '回復型': ['Healer', '回復型'],
  'バランス型': ['Balanced', '平衡型'],
  '防御型': ['Defender', '防禦型'],
  '限': ['Ltd', '限'],
  // stats and elements (names come from build_web.py)
  '力': ['STR', '力量'],
  '耐久': ['END', '耐久'],
  '器用': ['DEX', '靈巧'],
  '敏捷': ['AGI', '敏捷'],
  '魔力': ['MAG', '魔力'],
  '火': ['Fire', '火'],
  '地': ['Earth', '地'],
  '風': ['Wind', '風'],
  '水': ['Water', '水'],
  '雷': ['Thunder', '雷'],
  '光': ['Light', '光'],
  '闇': ['Dark', '闇'],
};

export function t(key, vars) {
  // "text|context" keys let one Japanese word have different translations; Japanese shows "text"
  let s = key.split('|')[0];
  if (lang !== 'ja' && D[key]) s = D[key][lang === 'en' ? 0 : 1];
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  return s;
}

// Run dates ("開催期間"), shown in JST like the game. Permanent ones (end ≥ 2030) show nothing.
const WEEK = { ja: '日月火水木金土', zh: '日一二三四五六' };
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
function jst(sec) {
  const d = new Date((sec + 9 * 3600) * 1000);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(), wd: d.getUTCDay(),
           hm: `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}` };
}
export function period(start, end, bare = false) {
  if (!start || !end) return '';
  const a = jst(start), b = jst(end);
  if (b.y >= 2030) return '';
  if (lang === 'en') {
    return `${bare ? '' : 'Event period: '}${DAY[a.wd]}, ${MON[a.m - 1]} ${a.d}, ${a.y} – ${DAY[b.wd]}, ${MON[b.m - 1]} ${b.d}${b.y !== a.y ? `, ${b.y}` : ''}, ${b.hm} JST`;
  }
  const w = WEEK[lang];
  const label = bare ? '' : (lang === 'zh' ? '活動期間' : '開催期間') + '：';
  const hm = lang === 'ja' ? b.hm.replace(':', '：') : b.hm;  // the game writes a full-width colon
  return `${label}${a.y}年${a.m}月${a.d}日（${w[a.wd]}）〜${b.y !== a.y ? `${b.y}年` : ''}${b.m}月${b.d}日（${w[b.wd]}）${hm}`;
}

// Static markup: data-i18n (text), data-i18n-title, data-i18n-placeholder.
export function applyStatic(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => (el.textContent = t(el.dataset.i18n)));
  root.querySelectorAll('[data-i18n-title]').forEach((el) => (el.title = t(el.dataset.i18nTitle)));
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => (el.placeholder = t(el.dataset.i18nPlaceholder)));
  const title = document.querySelector('title[data-i18n]');
  if (title) document.title = t(title.dataset.i18n);
}
