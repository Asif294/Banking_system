from django.db import models
from account.models import UserBankAccount
from django.contrib.auth.models import User
from .constance import TRANSACTIONS_TYPE
from django.conf import settings
class Transaction(models.Model):
    account=models.ForeignKey(UserBankAccount,related_name='transaction',on_delete=models.CASCADE)
    amount=models.DecimalField(decimal_places=2,max_digits=12)
    balance_after_transaction=models.DecimalField(decimal_places=2,max_digits=12)
    transaction_type=models.IntegerField(choices=TRANSACTIONS_TYPE,null=True)
    timestamp=models.DateTimeField(auto_now_add=True)
    loan_approve = models.BooleanField(default=False)

    class Meta:
        ordering=['timestamp']


    

