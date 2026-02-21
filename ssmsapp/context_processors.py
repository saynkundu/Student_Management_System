from .models import Notice # আপনার মডেলটি ইমপোর্ট করুন

def notice_count(request):
    # ডাটাবেস থেকে শুধু সেই নোটিশগুলো গুনবে যেগুলোর is_read=False
    count = Notice.objects.filter(is_read=False).count()
    
    # এটি একটি ডিকশনারি রিটার্ন করে যা সব টেম্পলেটে পাওয়া যাবে
    return {
        'new_notices_count': count
    }