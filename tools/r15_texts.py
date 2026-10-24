"""Round 15: every on-screen text of 小小魔法師 in English, Traditional Chinese, Japanese and
French (the language option; translations by Claude).

Each language is complete on its own: the English game shows English only (round 14 had
mixed in 小小魔法師 and the Chinese names / titles).

TEXTS[widget][TextBlock name] = (EN, ZH, JA, FR)      static texts, set by ApplyLanguage
RUNTIME = [(widget, graph, node title, pin, English literal, (EN, ZH, JA, FR))]
          literals the screens' own graphs set at runtime (results, status line, spell states)
CUTIN[key] = per language (tag, big name, subtitle) for the ultimate cut-in cards
"""
LANGS = ['EN', 'ZH', 'JA', 'FR']
LANG_NAMES = ('English', '繁體中文', '日本語', 'Français')       # each in its own language

BRAND = ('LITTLE WIZARD  /  ARENA', '小小魔法師  /  競技場', 'ちいさな魔法使い  /  アリーナ', 'PETIT SORCIER  /  ARÈNE')
FOOTER = ('ELEMENTAL DUELS', '元素對決', 'エレメンタル・デュエル', 'DUELS ÉLÉMENTAIRES')
BACK = ('BACK', '返回', 'もどる', 'RETOUR')
BACK_ARROW = ('<  BACK', '<  返回', '<  もどる', '<  RETOUR')
OPTIONS = ('OPTIONS', '設定', 'オプション', 'OPTIONS')
MAP_REF = ('MAP REFERENCE', '地圖一覽', 'マップ一覧', 'CARTES')
QUIT = ('EXIT GAME', '離開遊戲', 'ゲーム終了', 'QUITTER')

MAPS = {
    'Geometric': (('GEOMETRIC PLAYGROUND', '幾何遊樂場', 'ジオメトリック広場', 'TERRAIN GÉOMÉTRIQUE'),
                  ('Stepped paths and playful cover.', '階梯小路和好玩的掩體。', '段差のある道と楽しい遮蔽物。', 'Chemins en escalier et abris ludiques.')),
    'EmberRuins': (('EMBER RUINS', '熔岩遺跡', '残り火の遺跡', 'RUINES DE BRAISE'),
                   ('Long sightlines and ancient pillars.', '開闊的視野和古老的石柱。', '見通しのいい道と古代の柱。', 'Longues lignes de vue et piliers antiques.')),
    'FrostGarden': (('FROST GARDEN', '霜之花園', '霜の庭園', 'JARDIN DE GIVRE'),
                    ('Crystal cover in a diamond arena.', '菱形競技場裡的水晶掩體。', 'ひし形のアリーナに水晶の遮蔽物。', 'Abris de cristal dans une arène en losange.')),
    'SkyGrove': (('SKY GROVE', '天空樹林', '空の森', 'BOSQUET CÉLESTE'),
                 ('Two groves linked by a wide bridge.', '兩片樹林由一座寬橋相連。', '2つの森を広い橋がつなぐ。', 'Deux bosquets reliés par un large pont.')),
    'NeonFoundry': (('NEON FOUNDRY', '霓虹工廠', 'ネオン工場', 'FONDERIE NÉON'),
                    ('Clean lanes and industrial cover.', '筆直的通道和工業掩體。', 'まっすぐな通路と工場の遮蔽物。', 'Allées nettes et abris industriels.')),
}

# the four wizards: element tag, name, epithet, traits, ultimate, ultimate description
WIZARDS = {
    'Fire': (('FIRE', '火元素', '炎属性', 'FEU'),
             ('BLAISE', '布萊茲', 'ブレイズ', 'BLAISE'),
             ('The Blazing Mage', '爆炎魔法師', '爆炎の魔法使い', 'Le mage flamboyant'),
             ('+10% max health.\nUltimates come more often when hurt.', '最大生命值 +10%。\n受傷時更容易拿到大招。',
              '最大体力 +10%。\n傷つくほど必殺技が出やすい。', "+10 % de santé max.\nUltime plus fréquent s'il est blessé."),
             ('ULTIMATE · BLAZE CANNON', '大招 · 爆炎巨砲', '必殺技 · ブレイズキャノン', 'ULTIME · CANON ARDENT'),
             ('One giant orb blasts straight ahead.', '向正前方轟出一顆巨大的法球。', '巨大な魔法球をまっすぐ放つ。', 'Un orbe géant fonce droit devant.')),
    'Ice': (('ICE', '冰元素', '氷属性', 'GLACE'),
            ('NEVE', '妮芙', 'ニーヴ', 'NEVE'),
            ('Heart of Deep Frost', '沉凍之心', '凍てつく心', 'Cœur de givre'),
            ('Enemy shots slow down near her.\nHold jump to hover in midair.', '靠近她的敵人子彈會變慢。\n在空中按住跳躍可以浮空。',
             '近くの敵の弾が遅くなる。\n空中でジャンプ長押しで浮ける。', "Tirs ennemis ralentis près d'elle.\nMaintiens Saut pour flotter."),
            ('ULTIMATE · FROST RING', '大招 · 霜之環', '必殺技 · フロストリング', 'ULTIME · ANNEAU DE GIVRE'),
            ('Charge, then burst a ring of orbs.', '蓄力後向四周炸出一圈法球。', '溜めてから、周りに魔法球を放つ。', "Charge, puis libère un anneau d'orbes.")),
    'Wind': (('WIND', '風元素', '風属性', 'VENT'),
             ('GALE', '蓋爾', 'ゲイル', 'GALE'),
             ('The Fleeting Shadow', '瞬影', '瞬影', "L'ombre fugace"),
             ('+15% move speed and shot speed.', '移動速度和子彈速度 +15%。', '移動速度と弾速 +15%。', '+15 % de vitesse de course et de tir.'),
             ('ULTIMATE · SHADOW DASH', '大招 · 影之衝刺', '必殺技 · シャドウダッシュ', "ULTIME · RUÉE DE L'OMBRE"),
             ('Turn into an orb and dash through foes.', '化身法球，衝穿敵人。', '魔法球になって敵を突き抜ける。', "Fonce en orbe à travers l'ennemi.")),
    'Lightning': (('LIGHTNING', '雷元素', '雷属性', 'FOUDRE'),
                  ('VOLTA', '沃爾妲', 'ヴォルタ', 'VOLTA'),
                  ('Rondo of Currents', '輪舞之流', '輪舞の流れ', 'Le rondo des courants'),
                  ('Blinks to reposition (30 s).\nCanceling enemy shots deals damage.', '可以閃現換位（冷卻 30 秒）。\n抵銷敵人的子彈時會造成傷害。',
                   'ブリンクで瞬間移動（30秒）。\n敵の弾を相殺するとダメージ。', 'Se téléporte pour se replacer (30 s).\nContrer un tir inflige des dégâts.'),
                  ('ULTIMATE · SKY STORM', '大招 · 天降雷暴', '必殺技 · スカイストーム', 'ULTIME · TEMPÊTE CÉLESTE'),
                  ('Call a storm down onto your aim.', '在準星的位置召喚雷暴。', '狙った場所に嵐を呼ぶ。', 'Fait tomber une tempête sur ta cible.')),
}
SPELL_NUM = {'Fire': '1', 'Ice': '2', 'Wind': '3', 'Lightning': '4'}
ELEMENT_SHORT = {'Fire': ('FIRE', '火', '炎', 'FEU'), 'Ice': ('ICE', '冰', '氷', 'GLACE'),
                 'Wind': ('WIND', '風', '風', 'VENT'), 'Lightning': ('LIGHTNING', '雷', '雷', 'FOUDRE')}

TEXTS = {
    'WBP_WizardMain': {
        'Brand': BRAND, 'Footer': FOOTER,
        'Eyebrow': ('FOUR ELEMENTS · ONE ARENA', '四種元素 · 一個競技場', '4つの元素 · ひとつのアリーナ', 'QUATRE ÉLÉMENTS · UNE ARÈNE'),
        'Title': ('LITTLE\nWIZARD', '小小\n魔法師', 'ちいさな\n魔法使い', 'PETIT\nSORCIER'),
        'PlayButtonLabel': ('PLAY', '開始遊戲', 'プレイ', 'JOUER'),
        'OptionsButtonLabel': OPTIONS, 'MapReferenceButtonLabel': MAP_REF, 'QuitButtonLabel': QUIT,
    },
    'WBP_WizardMode': {
        'Brand': BRAND, 'Footer': FOOTER, 'BackButtonLabel': BACK_ARROW,
        'Title': ('SELECT GAME MODE', '選擇遊戲模式', 'ゲームモードを選ぶ', 'CHOISIS LE MODE DE JEU'),
        'Hint': ('The host sets the rules for this room.', '這個房間的規則由房主決定。', 'この部屋のルールはホストが決めます。', "L'hôte fixe les règles de cette partie."),
        'LastStandButtonTitle': ('LAST STAND', '背水一戰', 'ラストスタンド', 'DERNIER DEBOUT'),
        'LastStandButtonSub': ('One life. Last wizard standing.', '只有一條命，撐到最後就贏。', '命はひとつ。最後まで生き残れ。',
                               'Une vie. Le dernier debout gagne.'),
        'LastStandButtonRules': ('No respawns\nThe final survivor wins', '不會復活\n最後倖存的人獲勝', '復活なし\n最後に残った人の勝ち',
                                 'Pas de réapparition\nLe dernier survivant gagne'),
        'TimedButtonTitle': ('TIMED DUEL', '限時決鬥', 'タイムデュエル', 'DUEL CHRONO'),
        'TimedButtonSub': ('Three minutes of magic.', '三分鐘的魔法對決。', '3分間の魔法バトル。', 'Trois minutes de magie.'),
        'TimedButtonRules': ('Fewest deaths wins\nTies compare rounded-up health', '倒下次數最少的人獲勝\n平手時比剩餘生命（無條件進位）',
                             '倒れた回数が一番少ない人の勝ち\n同数なら残り体力（切り上げ）で比べる',
                             'Le moins de défaites gagne\nÉgalité : on compare les PV (arrondis)'),
        'ContinueButtonLabel': ('CONTINUE TO MAPS', '繼續：選擇競技場', 'アリーナ選択へ', "CHOISIR L'ARÈNE"),
    },
    'WBP_MapSelect': {
        'Brand': BRAND, 'BackButtonLabel': BACK,
        'Title': ('CHOOSE YOUR ARENA', '選擇競技場', 'アリーナを選ぼう', 'CHOISIS TON ARÈNE'),
        'Hint': ('The host chooses the theme. Every round generates a fresh layout.', '主題由房主選擇，每一回合都會產生新的地形。',
                 'テーマはホストが選びます。ラウンドごとに新しい地形になります。', "L'hôte choisit le thème. Chaque manche génère une nouvelle carte."),
        'RandomButtonLabel': ('RANDOM ARENA', '隨機競技場', 'ランダム', 'ARÈNE ALÉATOIRE'),
    },
    'WBP_MapReference': {
        'Brand': BRAND, 'BackButtonLabel': BACK,
        'Title': MAP_REF,
        'Hint': ('Explore as a white wizard. Every visit generates a fresh layout.', '用白色魔法師自由探索，每次進入都會產生新的地形。',
                 '白い魔法使いで自由に探索。入るたびに新しい地形になります。', 'Explore en sorcier blanc. Chaque visite génère une nouvelle carte.'),
        'InfoTitle': ('EXPLORE AT YOUR OWN PACE', '慢慢探索吧', 'のんびり探索しよう', 'EXPLORE À TON RYTHME'),
        'InfoText': ('White wizard: hover and blink.\nSpells and blink recharge in 1 s.\nG: ready the Ultimate\nR: new layout  |  Tab: menu',
                     '白色魔法師：可以浮空和閃現。\n魔法和閃現 1 秒就恢復。\nG：準備大招\nR：新地形  |  Tab：選單',
                     '白い魔法使い：浮遊とブリンクができる。\n魔法とブリンクは1秒で回復。\nG：必殺技を準備\nR：新しい地形  |  Tab：メニュー',
                     "Sorcier blanc : lévitation et téléport.\nSorts et téléport rechargés en 1 s.\nG : préparer l'ultime\nR : nouvelle carte  |  Tab : menu"),
    },
    'WBP_WizardSelect': {
        'Brand': BRAND, 'Footer': FOOTER, 'BackButtonLabel': BACK_ARROW,
        'Title': ('CHOOSE YOUR WIZARD', '選擇你的魔法師', '魔法使いを選ぼう', 'CHOISIS TON SORCIER'),
        'Hint': ('Pick a wizard for this duel. Every wizard can cast all four magics (keys 1-4).',
                 '選一位魔法師來對決。每位魔法師都能使用四種魔法（1–4 鍵）。',
                 'この対決で使う魔法使いを選ぼう。どの魔法使いも4つの魔法（1〜4キー）を使えます。',
                 'Choisis un sorcier pour ce duel. Chaque sorcier maîtrise les quatre magies (touches 1 à 4).'),
    },
    'WBP_WizardResult': {
        'Brand': BRAND, 'Footer': FOOTER,
        'ResultKicker': ('MATCH RESULT', '對戰結果', '試合結果', 'RÉSULTAT DU MATCH'),
        'ResultTitle': ('ROUND COMPLETE', '回合結束', 'ラウンド終了', 'MANCHE TERMINÉE'),
        'ResultDetail': ('A little rest before the next duel.', '下一場決鬥前，先休息一下。', '次の対決の前にひと休み。', 'Une petite pause avant le prochain duel.'),
        'RestartButtonLabel': ('PLAY AGAIN', '再玩一次', 'もう一度', 'REJOUER'),
        'HostNote': ('Only the host can start the next match.', '只有房主可以開始下一場。', '次の試合はホストだけが始められます。',
                     "Seul l'hôte peut lancer le prochain match."),
        'QuitButtonLabel': ('QUIT GAME', '離開遊戲', 'ゲーム終了', 'QUITTER'),
    },
    'WBP_WizardOptions': {
        'Brand': BRAND, 'BackButtonLabel': BACK,
        'Title': OPTIONS,
        'Hint': ('Adjust the balance. Changes apply immediately and are saved.', '調整後會立刻生效，並自動儲存。',
                 '変更はすぐに反映され、自動で保存されます。', 'Les changements sont appliqués et enregistrés immédiatement.'),
        'MasterVolumeTitle': ('MASTER VOLUME', '主音量', '全体の音量', 'VOLUME GÉNÉRAL'),
        'MasterVolumeHint': ('All game audio', '所有的遊戲聲音', 'すべての音', 'Tout le son du jeu'),
        'MusicVolumeTitle': ('MUSIC', '音樂', '音楽', 'MUSIQUE'),
        'MusicVolumeHint': ('Menu and arena themes', '選單和競技場的音樂', 'メニューとアリーナの曲', 'Thèmes du menu et des arènes'),
        'EffectsVolumeTitle': ('SOUND EFFECTS', '音效', '効果音', 'EFFETS SONORES'),
        'EffectsVolumeHint': ('Spells, movement and impacts', '魔法、移動和命中', '魔法・移動・ヒット', 'Sorts, déplacements et impacts'),
        'InterfaceVolumeTitle': ('INTERFACE', '介面音效', 'インターフェース', 'INTERFACE'),
        'InterfaceVolumeHint': ('Buttons, countdown and results', '按鈕、倒數和結果', 'ボタン・カウントダウン・結果', 'Boutons, compte à rebours et résultats'),
        'MouseSensitivityTitle': ('MOUSE SENSITIVITY', '滑鼠靈敏度', 'マウス感度', 'SENSIBILITÉ DE LA SOURIS'),
        'MouseSensitivityHint': ('Camera turn speed', '鏡頭轉動的速度', 'カメラの回転速度', 'Vitesse de rotation de la caméra'),
        'LanguageTitle': ('LANGUAGE', '語言', '言語', 'LANGUE'),
        'LanguageHint': ('Menus and on-screen text', '選單和畫面上的文字', 'メニューと画面の文字', "Menus et textes à l'écran"),
        'LanguageValue': LANG_NAMES,
    },
    'WBP_PracticeMenu': {
        'Brand': BRAND,
        'Title': ('PRACTICE ARENA', '練習場', '練習場', "ARÈNE D'ENTRAÎNEMENT"),
        'Hint': ('G: ready the Ultimate  /  R: new layout  /  Spells recharge in 1 second', 'G：準備大招  /  R：新地形  /  魔法 1 秒恢復',
                 'G：必殺技を準備  /  R：新しい地形  /  魔法は1秒で回復', "G : préparer l'ultime  /  R : nouvelle carte  /  Sorts rechargés en 1 s"),
        'ResumeButtonLabel': ('RESUME', '繼續', '再開', 'REPRENDRE'),
        'OptionsButtonLabel': OPTIONS, 'MapsButtonLabel': MAP_REF,
        'MainButtonLabel': ('MAIN MENU', '主選單', 'メインメニュー', 'MENU PRINCIPAL'),
    },
    'WBP_WizardOverlay': {
        'MatchStatusCaption': ('MATCH', '對戰', '試合', 'MATCH'),
        'StatusText': ('WAITING FOR WIZARDS', '等待魔法師加入', '魔法使いを待っています', 'EN ATTENTE DES SORCIERS'),
    },
    'WBP_PlayerHUD': {
        'BlinkTitle': ('BLINK', '閃現', 'ブリンク', 'TÉLÉPORT'),
        'BlinkCountdown': ('READY', '就緒', 'OK', 'PRÊT'),
        'VitalsCaption': ('HEALTH', '生命', '体力', 'SANTÉ'),
    },
}
for _m, (_name, _desc) in MAPS.items():
    for _w in ('WBP_MapSelect', 'WBP_MapReference'):
        TEXTS[_w][_m + 'Name'] = _name
        TEXTS[_w][_m + 'Desc'] = _desc
for _el, (_tag, _name, _epithet, _traits, _ult, _desc) in WIZARDS.items():
    _s = TEXTS['WBP_WizardSelect']
    _s[_el + 'Element'], _s[_el + 'Name'], _s[_el + 'Subtitle'] = _tag, _name, _epithet
    _s[_el + 'Traits'], _s[_el + 'UltimateTitle'], _s[_el + 'UltimateDesc'] = _traits, _ult, _desc
    _s[_el + 'Action'] = ('SELECT  >', '選擇  >', '決定  >', 'CHOISIR  >')
    _s[_el + 'Element'] = _tag
    _o = TEXTS['WBP_WizardOverlay']
    _o[_el + 'SpellName'] = tuple('%s  %s' % (SPELL_NUM[_el], x) for x in ELEMENT_SHORT[_el])
    _o[_el + 'SpellStatus'] = ('READY', '就緒', '準備OK', 'PRÊT')

READY = ('READY', '就緒', '準備OK', 'PRÊT')
RUNTIME = [
    # result screen
    ('WBP_WizardResult', 'RefreshView', 'SetText (Text)', 'InText', 'A MAGICAL DRAW!', ('A MAGICAL DRAW!', '魔法平手！', '魔法の引き分け！', 'MATCH NUL !')),
    ('WBP_WizardResult', 'RefreshView', 'SetText (Text)', 'InText', 'Perfectly matched. One more duel?',
     ('Perfectly matched. One more duel?', '勢均力敵！再來一場？', '互角の勝負！もう一戦？', 'Parfaitement à égalité. Encore un duel ?')),
    ('WBP_WizardResult', 'RefreshView', 'SetText (Text)', 'InText', 'VICTORY!', ('VICTORY!', '勝利！', '勝利！', 'VICTOIRE !')),
    ('WBP_WizardResult', 'RefreshView', 'SetText (Text)', 'InText', 'A little wizard. A brilliant win.',
     ('A little wizard. A brilliant win.', '小小魔法師，大大的勝利。', '小さな魔法使いの、大きな勝利。', 'Petit sorcier, grande victoire.')),
    ('WBP_WizardResult', 'RefreshView', 'SetText (Text)', 'InText', 'DEFEAT', ('DEFEAT', '落敗', '敗北', 'DÉFAITE')),
    ('WBP_WizardResult', 'RefreshView', 'SetText (Text)', 'InText', 'Shake off the sparkles. Your next duel awaits.',
     ('Shake off the sparkles. Your next duel awaits.', '拍掉身上的火花，下一場決鬥在等你。', '火花をはらって、次の対決へ。',
      "Secoue les étincelles, ton prochain duel t'attend.")),
    ('WBP_WizardResult', 'RefreshView', 'Append', 'A', 'DEATHS  ', ('DEATHS  ', '倒下次數  ', '倒れた回数  ', 'DÉFAITES  ')),
    ('WBP_WizardResult', 'RefreshView', 'Append', 'B', '     /     FINAL HP  ',
     ('     /     FINAL HP  ', '     /     剩餘生命  ', '     /     残り体力  ', '     /     PV FINAUX  ')),
    # in-game overlay
    ('WBP_WizardOverlay', 'RefreshView', 'SetText (Text)', 'InText', 'GET READY!', ('GET READY!', '準備！', 'かまえて！', 'PRÊTS ?')),
    ('WBP_WizardOverlay', 'RefreshView', 'SetText (Text)', 'InText', 'THE DUEL IS ABOUT TO BEGIN',
     ('THE DUEL IS ABOUT TO BEGIN', '決鬥即將開始', 'まもなく対決開始', 'LE DUEL VA COMMENCER')),
    ('WBP_WizardOverlay', 'RefreshView', 'SetText (Text)', 'InText', 'LAST STAND  /  STAY ALIVE',
     ('LAST STAND  /  STAY ALIVE', '背水一戰  /  活下去', 'ラストスタンド  /  生き残れ', 'DERNIER DEBOUT  /  SURVIS')),
    ('WBP_WizardOverlay', 'RefreshView', 'Append', 'A', 'TIMED DUEL  /  ', ('TIMED DUEL  /  ', '限時決鬥  /  ', 'タイムデュエル  /  ', 'DUEL CHRONO  /  ')),
    ('WBP_WizardOverlay', 'RefreshView', 'SetText (Text)', 'InText', 'WAITING FOR WIZARDS',
     ('WAITING FOR WIZARDS', '等待魔法師加入', '魔法使いを待っています', 'EN ATTENTE DES SORCIERS')),
    ('WBP_WizardOverlay', 'RefreshView', 'SetText (Text)', 'InText', 'PRACTICE / G: SUPER / F1-F4: WIZARD',
     ('PRACTICE / G: ULTIMATE / F1-F4: WIZARD', '練習 / G：大招 / F1–F4：換角色', '練習 / G：必殺技 / F1〜F4：キャラ変更',
      'ENTRAÎNEMENT / G : ULTIME / F1-F4 : SORCIER')),
    ('WBP_WizardOverlay', 'RefreshSpellStates', 'SelectString', 'A', 'COOLDOWN', ('COOLDOWN', '冷卻中', 'クールダウン', 'RECHARGE')),
    ('WBP_WizardOverlay', 'RefreshSpellStates', 'SelectString', 'B', 'READY', READY),
    ('WBP_WizardOverlay', 'RefreshSpellStates', 'SelectString', 'A', 'SUPER READY', ('ULTIMATE READY', '大招就緒', '必殺技OK', 'ULTIME PRÊT')),
    # player HUD (blink)
    ('WBP_PlayerHUD', 'RefreshBlinkHUD', 'SetText (Text)', 'InText', 'READY', ('READY', '就緒', 'OK', 'PRÊT')),
    ('WBP_PlayerHUD', 'RefreshBlinkHUD', 'Append', 'B', ' s', (' s', ' 秒', ' 秒', ' s')),
]

# the ultimate cut-in cards: (tag, big name, subtitle line)
CUTIN = {
    'Blaise': {'EN': ('ULTIMATE', 'BLAISE', 'The Blazing Mage'), 'ZH': ('大招', '布萊茲', '「爆炎魔法師」'),
               'JA': ('必殺技', 'ブレイズ', '「爆炎の魔法使い」'), 'FR': ('ULTIME', 'BLAISE', '« Le mage flamboyant »')},
    'Neve': {'EN': ('ULTIMATE', 'NEVE', 'Heart of Deep Frost'), 'ZH': ('大招', '妮芙', '「沉凍之心」'),
             'JA': ('必殺技', 'ニーヴ', '「凍てつく心」'), 'FR': ('ULTIME', 'NEVE', '« Cœur de givre »')},
    'Gale': {'EN': ('ULTIMATE', 'GALE', 'The Fleeting Shadow'), 'ZH': ('大招', '蓋爾', '「瞬影」'),
             'JA': ('必殺技', 'ゲイル', '「瞬影」'), 'FR': ('ULTIME', 'GALE', '« L\'ombre fugace »')},
    'Volta': {'EN': ('ULTIMATE', 'VOLTA', 'Rondo of Currents'), 'ZH': ('大招', '沃爾妲', '「輪舞之流」'),
              'JA': ('必殺技', 'ヴォルタ', '「輪舞の流れ」'), 'FR': ('ULTIME', 'VOLTA', '« Le rondo des courants »')},
}
