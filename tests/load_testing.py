from locust import HttpUser, task, between
import uuid

class Load_testing(HttpUser):
    wait_time=between(0,1)

    @task
    def reg_login_logout(self):
        name=str(uuid.uuid4())
        self.client.post('reg', data={'name':name, 'password':'123'})
        self.client.post('login', data={'name':name, 'password':'123'})
        self.client.get('logout')