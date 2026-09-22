1. Strings
Use for: Cache, OTP, Tokens, Single Values
Command	Purpose
SET key value	Store a value
GET key	Retrieve a value
DEL key	Delete a key
EXISTS key	Check if key exists
EXPIRE key seconds	Set expiry
TTL key	Check remaining time


Example:
SET banner "Welcome"
GET banner
DEL banner
TTL banner
2. Hashes
Use for: User Profiles, Product Details
Command	Purpose
HSET	Store fields
HGET	Get one field
HGETALL	Get all fields


Example:
HSET user:1 name Hardik city Ghaziabad
HGET user:1 name
HGETALL user:1
3. Lists
Use for: Notifications, Queues, Recent Searches
Command	Purpose
LPUSH	Add at beginning
RPUSH	Add at end
LRANGE	Get items
LPOP	Remove from beginning
RPOP	Remove from end


Example:
LPUSH notifications "Hello"
LPUSH notifications "Welcome"

LRANGE notifications 0 -1

LPOP notifications
4. Sets
Use for: Online Users, Likes, Unique Values
Command	Purpose
SADD	Add member
SMEMBERS	Get all members
SISMEMBER	Check membership
SREM	Remove member


Example:
SADD online_users Hardik
SADD online_users Rahul

SMEMBERS online_users

SISMEMBER online_users Hardik

SREM online_users Rahul
5. Sorted Sets (ZSET)
Use for: Leaderboards, Rankings, Trending Posts
Command	Purpose
ZADD	Add member with score
ZRANGE	Lowest to highest score
ZREVRANGE	Highest to lowest score


Example:
ZADD leaderboard 100 Hardik
ZADD leaderboard 200 Rahul

ZREVRANGE leaderboard 0 -1 WITHSCORES
Data Structures Summary
Data Structure	Stores	Common Use Case
String	One value	Cache, OTP, Tokens
Hash	Object (field-value pairs)	User Profile
List	Ordered collection	Notifications, Queues
Set	Unique unordered values	Likes, Online Users
Sorted Set	Unique values + score	Leaderboards