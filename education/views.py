from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def tiktok_feed(request):
    return render(request, 'tiktok/feed.html')

@login_required
def instagram_feed(request):
    return render(request, 'instagram/feed.html')

@login_required
def snapchat_feed(request):
    return render(request, 'snapchat/feed.html')

@login_required
def facebook_feed(request):
    return render(request, 'facebook/feed.html')