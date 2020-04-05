# coding: utf-8
# bot定期動作

# 読込
import sys
import os
import logging
import json
import datetime
import codecs
import random
from requests_oauthlib import OAuth1Session
from config import *

# 定数
UPDATE_URL = "https://api.twitter.com/1.1/statuses/update.json"
RETWEET_URL = "https://api.twitter.com/1.1/statuses/retweet/{id}.json"
SEARCH_URL = "https://api.twitter.com/1.1/search/tweets.json"

SEARCH_Q = " exclude:retweets filter:media since:{yesterday}_23:30:00_JST until:{today}_23:30:00_JST"
CURRENT_PATH = f"{os.path.dirname(os.path.abspath(__file__))}/"
BOT_PATH = ""

"""
コマンドライン引数について
[0]		当ファイル
[1]		企画種別
[2]		動作内容
"""

def TwitterAPI_post(twitter, URL, params, LogTxt):
	req = twitter.post(URL, params = params)
	# ログ出力
	ResultLogging(req, LogTxt)
	return req

def TwitterAPI_get(twitter, URL, params, LogTxt):
	req = twitter.get(URL, params = params)
	# ログ出力
	ResultLogging(req, LogTxt)
	return req

def ResultLogging(req, LogTxt):
	if req.status_code == 200:
		LogTxt += "Succeed"
	else:
		textJson = json.loads(req.text)
		LogTxt += "ERROR : (" + str(req.status_code) + ")<" + str(textJson["errors"][0]["code"]) + ">　" + textJson["errors"][0]["message"]
	logger.info(LogTxt)

try:
	# ログ設定
	logging.basicConfig(filename=f"{CURRENT_PATH}LOG.log" \
		, level=logging.INFO \
		, format="%(asctime)s	%(message)s")
	logging.getLogger("__main__").setLevel(logging.INFO)
	logger = logging.getLogger(__name__)

	# コマンドラインチェック
	if len(sys.argv) != 3:
		logger.info("コマンドラインチェック異常")
		exit()

	# 動作bot
	bot = None
	if sys.argv[1] == "OneMMD":
		bot = bot_OneMMD
		SEARCH_Q = "#深夜の真剣MMD60分一本勝負" + SEARCH_Q
	elif sys.argv[1] == "5MMD":
		bot = bot_5MMD
		SEARCH_Q = "#深夜の真剣MMD5分一本勝負" + SEARCH_Q
	else:
		logger.info("動作botチェック異常")
		exit()
	
	# 認証
	twitter = OAuth1Session(bot.CONSUMER_KEY, bot.CONSUMER_SECRET, bot.ACCESS_TOKEN, bot.ACCESS_TOKEN_SECRET)
	BOT_PATH = CURRENT_PATH + bot.BOT_PATH + "/"
	LogTxt = f"{sys.argv[2]}："

	# お題通知は別処理
	TweetString = ""
	if sys.argv[2] == "Announcement":
		"""
		お題通知
		"""
		# テンプレート読取
		with codecs.open(BOT_PATH + "Rule.txt", "r", "utf-8") as tmp:
			rule = tmp.read()

		# 12/31分岐
		if datetime.date.today().strftime("%m/%d") == "12/31":
			# 自由お題通知
			year = datetime.date.today().strftime("%Y")
			rule = rule.replace("{Theme}", f"{year}年最後のお題は自由です。これだ！と思う物を作りましょう。")
		else:
			# 通常告知
			# リスト読取
			with codecs.open(BOT_PATH + "WinCharaList.txt", "r", "utf-8") as tmp:
				WinNameList = tmp.readlines()
			with codecs.open(BOT_PATH + "OldCharaList.txt", "r", "utf-8") as tmp:
				OldNameList = tmp.readlines()
			AllNameList = []
			AllNameList.extend(WinNameList)
			AllNameList.extend(OldNameList)

			# 直近日付リスト読取
			with codecs.open(BOT_PATH + "LastChara.txt", "r", "utf-8") as tmp:
				RemovalList = tmp.readlines()
			
			# 再抽選チェック
			RandomNameList = []
			while True:
				# リストから3名をランダム抽出
				RandomNameList = random.sample(AllNameList, 3)
				
				# 直近日付チェック
				if len(set(RandomNameList) & set(RemovalList)) != 0:
					continue
				
				# 旧作キャラ2つ以上チェック
				if len(set(RandomNameList) & set(OldNameList)) >= 2:
					continue
				
				# ここまで来ればOK
				break
			
			# お題格納
			rule = rule.replace("{Theme}", \
				RandomNameList[0].replace("\n","") + "、" + RandomNameList[1].replace("\n","") + "、" + RandomNameList[2].replace("\n",""))

			# 直近日付リスト書込
			if len(RemovalList) >= bot.LAST_DATE * 3:
				del RemovalList[:3]
			RemovalListstr = ""
			for RemStr in RemovalList:
				RemovalListstr += RemStr.replace("\n","") + "\n"
			for RemStr in RandomNameList:
				RemovalListstr += RemStr.replace("\n","") + "\n"
			with codecs.open(BOT_PATH + "LastChara.txt", "w", "utf-8") as tmp:
				tmp.write(RemovalListstr)
		
		# 次の開催日埋め込み
		# 次回開催日にツイートするのでtoday
		TweetString = rule.replace("{Time}", datetime.date.today().strftime("%m/%d"))

		# ツイート
		params = {"status" : TweetString}
		req = TwitterAPI_post(twitter, UPDATE_URL, params, LogTxt)
		
		# TweetID控え
		if req.status_code == 200:
			with codecs.open(BOT_PATH + "ThemeTweet.txt", "w", "utf-8") as tmp:
				textJson = json.loads(req.text)
				tmp.write(textJson["id_str"])

	elif sys.argv[2] == "ThemeRT":
		"""
		お題ツイートRT
		"""
		path = BOT_PATH + "ThemeTweet.txt"
		if os.path.exists(path):
			with codecs.open(BOT_PATH + "ThemeTweet.txt", "r", "utf-8") as tmp:
				tweetID = tmp.read()
				params = {"id" : tweetID}
				TwitterAPI_post(twitter, RETWEET_URL.format(id=tweetID), params, LogTxt)

	elif sys.argv[2] == "CreationRT":
		"""
		作品RT
		"""
		# 作品検索
		params = {"q" : SEARCH_Q.format(yesterday=(datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), today=(datetime.date.today()).strftime("%Y-%m-%d")), \
			"result_type" : "recent", \
			"count" : "100", \
			}
		req = TwitterAPI_get(twitter, SEARCH_URL, params, LogTxt)
		
		# RT
		textJson = json.loads(req.text)
		for item in textJson["statuses"]:
			# RT済はパス
			if item["retweeted"]:
				continue
			params = {"id" : item["id"]}
			TwitterAPI_post(twitter, RETWEET_URL.format(id=item["id_str"]), params, LogTxt)

	else:	
		"""
		その他通知
		"""
		# ファイル内容をツイートするだけ
		with codecs.open(f"{BOT_PATH}{sys.argv[2]}.txt", "r", "utf-8") as tmp:
			TweetString = tmp.read()

		# ツイート
		params = {"status" : TweetString}
		TwitterAPI_post(twitter, UPDATE_URL, params, LogTxt)

except:
	import traceback
	logger.exception(traceback.print_exc())
