// MongoDB 초기화 스크립트
// currency_db 데이터베이스와 사용자 생성

// currency_db 데이터베이스로 전환
db = db.getSiblingDB('currency_db');

// trip_user 사용자 생성 (애플리케이션용)
db.createUser({
  user: 'trip_user',
  pwd: 'trip-service-mongo',
  roles: [
    { role: 'readWrite', db: 'currency_db' },
    { role: 'dbAdmin', db: 'currency_db' }
  ]
});

// admin 사용자 생성 (관리용)
db.createUser({
  user: 'admin',
  pwd: 'password',
  roles: [
    { role: 'readWrite', db: 'currency_db' },
    { role: 'dbAdmin', db: 'currency_db' }
  ]
});

// 테스트 컬렉션 생성
db.createCollection('country_clicks');
db.createCollection('user_selections');

// 초기 데이터 삽입 (테스트용)
db.country_clicks.insertOne({
  country_code: 'KR',
  country_name: 'South Korea',
  daily_clicks: 0,
  total_clicks: 0,
  date: '2025-09-17',
  created_at: new Date(),
  last_updated: new Date()
});

print('MongoDB initialization completed successfully');
print('Database: currency_db');
print('Application User: trip_user');
print('Application Password: trip-service-mongo');
print('Admin User: admin');
print('Admin Password: password');
