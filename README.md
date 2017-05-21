# muti-livechat

## 数据交换说明
* 加入房间
```json
{
  'msgtype': 'join'
  'username': nick
  'payload': 'joined the chat room'
}
```
* 发送消息
```json
{
  'msgtype':'text'
  'username': nick
  'payload': message
}
```
* 离开房间
```json
{
  'msgtype':'leave'
  'username': nick
  'payload': 'left the chat room'
}
```
* 房间用户列表
```json
{
  'msgtype':'nick_list'
  'username': nick
  'payload': [room-nick-lists]
}
```
## redis using
#### max room number key 'live-chat-sys-max-room'
* 用于热更新最大房间数
#### max users per room key 'live-chat-sys-max-room-users'
* 用于热更新每个房间最大用户数
#### a set key members-rooms
* 存储房间名称 通过redis.sadd 添加集合成员
#### a set key members-[roomname]-users
```python
'members-%s-users' % (room)
```
* 存储一个房间下的用户名称， 通过redis.sadd 添加集合成员
####  key [client_id]+'room'
* 用于session id 关联房间名称，key : [client_id]+'room' ,value : roomname
####  key [client_id]+'nick'
* 用于session id 关联用户名称，key : [client_id]+'nick' ,vaulue : nickname
####  PUB/SUB channel
* 使用房间名称做 发布订阅channel名，解决多房间管理下消息分组广播问题
## API 认证
* 提供两种认证模式
* 登录第三方如weibo 授权认证模式，采用oauth2协议，通过第三方登录，用户授权后，返回access_token 给客户端，客户端携带asses_token请求服务
* 使用用户名，密码登录 账户认证系统，成功后返回token给客户端，客户端携带asses_token请求服务
