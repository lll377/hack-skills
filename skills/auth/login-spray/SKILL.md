---
name: login-spray
description: >-
  Generic login spray for any AI. First decide if this login can be judged,
  recover client-side password encryption when the field is not plaintext,
  then run the fixed dictionary order. Skip when success cannot be told from failure.
---

# login-spray

一次只打一个「会校验用户名和密码」的登录口。先判断，再打。判断不了成败，就写报告并换下一个资产。

`wordlist/` 只读。这个资产的过滤、加密、进度、报告只写 `evidence/<目标>/spray/`。不改密码。不发 PUT、DELETE。

## 判断

按顺序做。一条不过就跳过，不打。

1. 找到真正校验口令的那条请求。表单后面还有接口，打接口。只有扫码或跳转、没有密码字段：跳过。
2. 看这条请求里的密码是不是人刚输入的原文。
   - 是原文：用户名写 `{{user}}`，密码写 `{{pass}}`。
   - 不是原文：到本页 JS 找出算法。同一段明文算出来的长度和编码，要和浏览器那一发一致。写成 `spray/encrypt.py` 里的 `transform(user, password)`，返回的字典至少含 `pass`。模板加上这个文件的路径。算不出、在原生代码里、或对不上：跳过。
3. 每发都变的 csrf、随机串，在 `transform` 里现取。取不到：跳过。
4. 用不存在的用户和固定错密打两次。两次对不上：跳过。两次都是验证码、滑块或短信，换一个密码这句话不变：跳过。
5. 分清账号锁定和 IP 频率。写了错几次锁账号，每个用户的口令数就停在这个次数以下。只卡 IP 就放慢，不整站跳过。没写次数，第 1 段按每个用户 2 个口令打。

## 打中

不要只看状态码或长度。

- 能进业务口：错密句消失，同一对再打仍消失，不带会话打确认口没有确认句，带上新会话才有。`hit` 写 `session`。
- 口令对了但被多因素或改密挡住：错密句消失且再打仍消失，就算打中。`hit` 写 `split`。报告写「口令已分开，未进业务」。

## 字典

只滤密码副本。页面或回包写了长度、数字、大写、小写、特殊字符才删。没写不删。用户名不按口令规则删。某一段滤完是 0 对，跳过这一段。

1. `wordlist/pass/top2.txt` × `wordlist/user/常用密码+用户名+首字母+姓.txt`。大表只配 top2。
2. `wordlist/pass/top10.txt` × `wordlist/user/常见用户名.txt`，全组合。
3. `wordlist/pass/top10.txt` × `wordlist/user/常见姓名3000.txt`，全组合。
4. `wordlist/pass/top10.txt` × 上面两个用户表的并集。打过的对跳过。
5. 只有枚举到的用户 × `wordlist/pass/top100.txt`。
6. 只打用户名 `admin`，密码用 `wordlist/admin.txt`。
7. 枚举到或已打中的用户才做。种子是用户名、主机第一段、已中口令。用仓库根 `hashcat 规则.txt` 生成后再滤。没有这类用户就跳过。

某一段因锁定或频率停下，只停这一段。后面的段继续。已锁用户从后面去掉。

## 执行

只用 `bin/python tools/src_spray.py`，不要另写爆破脚本。默认走 Burp `http://127.0.0.1:8080`，间隔 1 秒。

1. `template.json`：`url`、`method`、`headers`、`body`。有加密或现取令牌就加 `encrypt`。
2. `baseline --template template.json --out spray/baseline.json`。不稳就跳过。
3. `judge.json`：`fail_phrase`、`fail_status`、`hit`、`stop_phrases`。`session` 再写 `confirm` 的 `url`、`pass_phrase`、`value_from`、`header`。
4. `plan --out spray`。有规则再加 `--min-len`、`--max-len`、`--need`、`--note`。有枚举用户再加 `--enum`。
5. 按段 `run --baseline spray/baseline.json --template template.json --judge judge.json --pairs spray/pairs/stageN.txt --progress spray/progress/stageN.json --log spray/log/stageN.jsonl`。
6. 第 7 段先 `mutate --users spray/stage7.users --seeds spray/stage7.seeds --out spray/pairs/stage7.txt`，再 `run`。
7. `report --dir spray --url 登录URL --template 模板路径 --fail-status --fail-phrase --pass-phrase`。

每个资产一份 `spray/report.md`。跳过写停在哪一步。打过的写每段条数、实打、命中、中断、从哪一行续。命中写用户名和口令。人工续打不换字典。
