from django.shortcuts import render
from django.views.generic import CreateView,ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Transaction
from .forms import DepositeForm,WithdrawFrom,LoanRequestForm
from .constance import DEPOSIT,WITHDRAWAL,LOAN ,LOAN_PAID
from django.contrib import messages
from django.http import HttpResponse
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage,EmailMultiAlternatives
from django.template.loader import render_to_string
from django.db.models import Sum
from django.shortcuts import get_object_or_404,redirect
from django.views import View
from django.urls import reverse_lazy
from django.views.generic.edit import FormView
from django.contrib.auth.decorators import login_required
from .models import UserBankAccount, Transaction
from .forms import TransferForm
from .constance import (
    TRANSACTION_TYPE_TRANSFER_OUT,
    TRANSACTION_TYPE_TRANSFER_IN,
)

def send_transaction_email(user, amount, subject, template):
        message = render_to_string(template, {
            'user' : user,
            'amount' : amount,
        })
        send_email = EmailMultiAlternatives(subject, '', to=[user.email])
        send_email.attach_alternative(message, "text/html")
        send_email.send()

class TransactionCreateMixin(LoginRequiredMixin,CreateView):
    template_name='transactions/transaction_form.html'
    model=Transaction
    title=''
    success_url=reverse_lazy('transaction_report')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.account
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) # template e context data pass kora
        context.update({
            'title': self.title
        })
        return context

class DepositMoneyView(TransactionCreateMixin):
    form_class=DepositeForm
    title='Deposit'

    def get_initial(self):
        initial={'transaction_type':DEPOSIT}
        return initial
    
    def form_valid(self,form):
        amount=form.cleaned_data.get('amount')
        account=self.request.user.account
        account.balance+=amount
        account.save(
            update_fields=['balance']
        )

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully'
        )
        send_transaction_email(self.request.user, amount, "Deposite Message", "transactions/deposite_email.html")
        return super().form_valid(form)

class WithdrawMoneyView(TransactionCreateMixin):
    form_class=WithdrawFrom
    title='Withdraw'

    def get_initial(self):
        initial={'transaction_type':WITHDRAWAL}
        return initial
    
    def form_valid(self,form):
        amount=form.cleaned_data.get('amount')
        account=self.request.user.account
        account.balance-=amount
        account.save(
            update_fields=['balance']
        )

        messages.success(
            self.request,
            f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ from your account'
        )
        send_transaction_email(self.request.user, amount, "Withdrawal Message", "transactions/withdrawal_email.html")
        return super().form_valid(form)


class LoneRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = 'Request For Loan'

    def get_initial(self):
        initial = {'transaction_type': LOAN}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account,
            transaction_type=LOAN,
            loan_approve=True  # Ensure this matches the model field name
        ).count()
        if current_loan_count >= 3:
            return HttpResponse("You have crossed your limits")

        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully'
        )
        send_transaction_email(self.request.user, amount, "Loan Request Message", "transactions/loan_email.html")
        return super().form_valid(form)

class TransactionReportView(LoginRequiredMixin,ListView):
    template_name="transactions/transaction_report.html"
    model = Transaction
    balance=0
    context_object_name='report_list '

    def get_queryset (self):
        queryset=super().get_queryset().filter(
            account=self.request.user.account
        )

        start_date_str=self.request.GET.get('start_date')
        end_date_str=self.request.GET.get('end_date')

        if start_date_str and end_date_str:
            start_date=datetime.strptime(start_date_str,"%Y-%m-%d").date()
            end_date=datetime.strptime(end_date_str,"%Y-%m-%d").date()
            queryset = queryset.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)
            

            self.balance=Transaction.objects.filter(timestamp__date__gte=start_date,timestamp__date__lte=end_date).aggregate(Sum('amount'))['amount__sum']
        else:
            self.balance=self.request.user.account.balance
        
        return queryset.distinct()
    def get_context_data(self,**kwargs):
        context=super().get_context_data(**kwargs)
        context.update({
            'account' :self.request.user.account
        })
        return context
    

class PayLoanView(LoginRequiredMixin, View):
    def get(self, request, loan_id):
        loan = get_object_or_404(Transaction, id=loan_id)
        print(loan)
        if loan.loan_approve:
            user_account = loan.account
                # Reduce the loan amount from the user's balance
                # 5000, 500 + 5000 = 5500
                # balance = 3000, loan = 5000
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approved = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect('loan_list')
            else:
                messages.error(
            self.request,
            f'Loan amount is greater than available balance'
        )

        return redirect('loan_list')
class LoanListView(LoginRequiredMixin,ListView):
    model = Transaction
    template_name = 'transactions/loan_request.html'
    context_object_name = 'loans' # loan list ta ei loans context er moddhe thakbe
    
    def get_queryset(self):
        user_account = self.request.user.account
        queryset = Transaction.objects.filter(account=user_account,transaction_type=3)
        print(queryset)
        return queryset
    

class TransferAmountView(LoginRequiredMixin, FormView):
    template_name = 'transactions/transfer_money.html'
    form_class = TransferForm
    success_url = reverse_lazy('transfer_amount')

    def form_valid(self, form):
        from_account = UserBankAccount.objects.get(user=self.request.user)
        to_account = form.cleaned_data['to_account']
        amount = form.cleaned_data['amount']
        
        if from_account == to_account:
            messages.error(self.request, "Cannot transfer money to the same account.")
            return self.form_invalid(form)

        if from_account.balance < amount:
            messages.error(self.request, "Insufficient balance to perform this transfer.")
        else:
          
            from_account.balance -= amount
            from_account.save()
            
            to_account.balance += amount
            to_account.save()
            Transaction.objects.create(
                account=from_account,
                amount=-amount,
                balance_after_transaction=from_account.balance,
                transaction_type=TRANSACTION_TYPE_TRANSFER_OUT
            )

            Transaction.objects.create(
                account=to_account,
                amount=amount,
                balance_after_transaction=to_account.balance,
                transaction_type=TRANSACTION_TYPE_TRANSFER_IN
            )

            messages.success(self.request, "Amount transferred successfully.")
            send_transaction_email(self.request.user, amount, "Loan Request Message", "transactions/transfer_email.html")
            return super().form_valid(form)
        
