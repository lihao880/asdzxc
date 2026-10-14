<?php
// ===== 咪咕直播代理（基于 develop202 算法，2026 可用）=====

// 代理调用方式： http://IP/migu.php?pid=608807420

function http_get($url, $headers = array(), $follow = true, $timeout = 15, $returnHeaders = false) {
    $ch = curl_init();
    $opts = array(CURLOPT_URL => $url, CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => $timeout,
        CURLOPT_SSL_VERIFYPEER => false, CURLOPT_SSL_VERIFYHOST => false);
    if ($headers) $opts[CURLOPT_HTTPHEADER] = $headers;
    if ($follow) $opts[CURLOPT_FOLLOWLOCATION] = true;
    if ($returnHeaders) $opts[CURLOPT_HEADER] = true;
    curl_setopt_array($ch, $opts);
    $r = curl_exec($ch);
    $info = curl_getinfo($ch);
    curl_close($ch);
    return array($r, $info);
}

function get_play_url($pid, $rateType = 3) {
    $t = sprintf('%.0f', microtime(true) * 1000);
    $v = "2600034600";
    $vid = $v . "-99000-201600010010028";
    $cid = md5($t);
    $h = array("AppVersion: " . $v, "TerminalId: android", "X-UP-CLIENT-CHANNEL-ID: " . $vid, "ClientId: " . $cid);
    if ($pid != "641886683" && $pid != "641886773") $h[] = "appCode: miguvideo_default_android";
    $s = $t . $pid . substr($v, 0, 8);
    $m = md5($s);
    $salt = str_pad((string)mt_rand(0, 999999), 6, '0', STR_PAD_LEFT) . "25";
    $sfx = "2cac4f2c6c3346a5b34e085725ef7e33migu" . substr($salt, 0, 4);
    $sign = md5($m . $sfx);
    $u = "https://play.miguvideo.com/playurl/v1/play/playurl?sign=" . $sign . "&rateType=" . $rateType
        . "&contId=" . $pid . "&timestamp=" . $t . "&salt=" . $salt
        . "&flvEnable=true&super4k=true&h265N=true&4kvivid=true&2Kvivid=true&vivid=2";
    list($r) = http_get($u, $h);
    $j = json_decode($r, true, 512, JSON_BIGINT_AS_STRING);
    if (!isset($j['body']['urlInfo']['url'])) return null;
    $url = $j['body']['urlInfo']['url'];
    if (!preg_match('/&puData=([^&]+)/', $url, $mm)) return null;
    $pu = $mm[1];
    $dd = get_ddcalcu($pu, $pid);
    return $url . '&ddCalcu=' . $dd . '&sv=10004&ct=android';
}

function get_ddcalcu($puData, $pid) {
    $keys = "cdabyzwxkl";
    $dd = "";
    $n = strlen($puData);
    for ($i = 0; $i < $n / 2; $i++) {
        $dd .= $puData[$n - $i - 1] . $puData[$i];
        if ($i == 1) $dd .= "v";
        if ($i == 2) $dd .= $keys[substr(date('Ymd'), 2, 1)];
        if ($i == 3) $dd .= $keys[substr($pid, 6, 1)];
        if ($i == 4) $dd .= "a";
    }
    return $dd;
}

function resolve_playurl($pid, $rateType = 3) {
    $pre = get_play_url($pid, $rateType);
    if (!$pre) return null;
    // 循环跟随 302 Location，直到得到最终可播地址
    $cur = $pre;
    for ($i = 0; $i < 6; $i++) {
        list($r, $info) = http_get($cur, array("User-Agent: MiguVideo/6.2.30"), false, 15, true);
        $loc = null;
        if (preg_match('/^Location: (.*)$/mi', $r, $lm)) $loc = trim($lm[1]);
        if (!$loc || $info['http_code'] != 302) return $cur;
        if (strpos($loc, 'http://bofang') === 0) return $cur;
        $cur = $loc;
    }
    return $cur;
}

// ===== 输出 =====
$want_pid = isset($_GET['pid']) ? $_GET['pid'] : null;
if ($want_pid) {
    $loc = resolve_playurl($want_pid);
    if (!$loc) { http_response_code(502); exit("获取失败"); }
    header("Location: " . $loc);
    exit;
}

// 频道列表
header("Content-Type: text/plain; charset=utf-8");
$root = "1ff892f2b5ab4a79be6e25b69d2f5d05";
list($r) = http_get("https://program-sc.miguvideo.com/live/v2/tv-data/" . $root);
$j = json_decode($r, true, 512, JSON_BIGINT_AS_STRING);
$liveList = isset($j['body']['liveList']) ? $j['body']['liveList'] : array();
$filtered = array();
foreach ($liveList as $c) {
    if (!isset($c['name']) || $c['name'] != "热门") $filtered[] = $c;
}
usort($filtered, function($a, $b) {
    $na = isset($a['name']) ? $a['name'] : '';
    $nb = isset($b['name']) ? $b['name'] : '';
    if ($na == "央视") return -1;
    if ($nb == "央视") return 1;
    return 0;
});

echo "#EXTM3U x-tvg-url=\"https://develop202.github.io/migu_video/playback.xml\"\n";
$scheme = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] != 'off') ? 'https' : 'http';
$host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'localhost';
$uri = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '';
$self = $scheme . "://" . $host . strtok($uri, '?');
foreach ($filtered as $cat) {
    $cid = isset($cat['vomsID']) ? $cat['vomsID'] : '';
    if (!$cid) continue;
    list($r2) = http_get("https://program-sc.miguvideo.com/live/v2/tv-data/" . $cid);
    $j2 = json_decode($r2, true, 512, JSON_BIGINT_AS_STRING);
    $dataList = isset($j2['body']['dataList']) ? $j2['body']['dataList'] : array();
    foreach ($dataList as $ch) {
        $name = isset($ch['name']) ? $ch['name'] : '?';
        $pid = isset($ch['pID']) ? $ch['pID'] : null;
        if (!$pid) continue;
        $logo = (isset($ch['pics']['highResolutionH'])) ? $ch['pics']['highResolutionH'] : '';
        $catname = isset($cat['name']) ? $cat['name'] : '';
        echo "#EXTINF:-1 tvg-id=\"" . $name . "\" tvg-name=\"" . $name . "\" tvg-logo=\"" . $logo . "\" group-title=\"" . $catname . "\"," . $name . "\n";
        echo $self . "?pid=" . $pid . "\n";
    }
}