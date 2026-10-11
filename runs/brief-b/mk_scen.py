import json
K='api_account_response.data.products.'
def acct(now, prods):
    v={'now':now,'title':'Mr','last_name':'Reyes','customer_id':'c1','st':'id_phone','pending':'account','r_ok':'True'}
    for i,p in enumerate(prods):
        for k,x in p.items(): v[K+'%d.%s'%(i,k)]=x
    return v
CC={'product_id':'p1','type':'credit_card','card_last4':'4821','past_due':500,'days_late':14,'minimum_payment':50}
PL={'product_id':'p2','type':'personal_loan','past_due':300,'days_late':3,'instalment_amount':120}
CL={'product_id':'p3','type':'car_loan','past_due':900,'days_late':30,'instalment_amount':450}
def P(id,typ,due,fl,dl,band,att,deadline,**kw):
    d={'id':id,'type':typ,'card_last4':'4821' if typ=='credit_card' else '','past_due':due,'days_late':dl,'floor':fl,'band':band,'attempts':att,'deadline':deadline,
       'used':0,'floor_offered':0,'too_much':0,'vague':0,'dl_offered':0,'status':'open','date':'','amount':0.0,'offer_date':'','offer_amount':0.0,'note':'','note_done':0}
    d.update(kw); return d
def st(now, stage, Ps, **kw):
    v={'now':now,'title':'Mr','last_name':'Reyes','customer_id':'c1','st':stage,'P_json':json.dumps(Ps),'verified':'yes','idx':0,'q':'Q?'}
    for f in ['intent','dob_day','dob_month','dob_year','digits','when_words','time_words','amount','product_ref']: v[f]='none'
    v.update(kw); return v
W='2026-10-14T11:00'; F='2026-10-16T11:00'; H='2026-10-23T11:00'
pcc=lambda **k: P('p1','credit_card',500,50,14,'late',2,'2026-10-23',**k)
ppl=lambda **k: P('p2','personal_loan',300,120,3,'early',1,'2026-11-02',**k)
S=[]
def s(name,rules,run,vars,expect): S.append({'name':name,'rules':rules,'run':run,'vars':vars,'expect':expect})
s('opening sentence',[1,2],['init'],{'title':'Mr','last_name':'Reyes'},{'say':'Hello, I am a digital assistant calling from Freya Bank. We are recording this call. Am I speaking with Mr Reyes?'})
s('account 2 products: bands and deadlines, state each',['B1','B2','B3',16,17,18,28,'B4'],['brain'],acct(W,[CC,PL]),
  {'st':'today','say':{'contains':'credit card ending 4821 has a past-due amount of 500.00 and is 14 days late. Your personal loan has a past-due amount of 300.00 and is 3 days late. Can you make these payments today?'},
   'P_json':{'contains':'"deadline": "2026-11-02"'}})
s('late deadline 7bd from Wed',[18],['brain'],acct(W,[CC]),{'P_json':{'contains':'"deadline": "2026-10-23"'},'say':{'contains':'Can you make this payment today?'}})
s('late deadline from Friday 16 Oct (holiday 26th skipped)',[18],['brain'],acct(F,[CC]),{'P_json':{'contains':'"deadline": "2026-10-28"'}})
s('account fail retries once',[37],['brain'],dict(acct(W,[]),r_ok='pending'),{'act':'account','fails_account':1})
s('account fail twice closes service error',[37],['brain'],dict(acct(W,[]),r_ok='pending',fails_account=1),{'outcome':'no_promise','reason':'service_error','act':'end'})
s('no today -> attempt 1 on Friday for first product',['B4',30,28],['brain'],st(W,'today',[pcc(),ppl()],intent='no'),{'st':'prod','say':{'contains':'credit card ending 4821: could you pay 500.00 on Friday 16 October'}})
s('no today on Friday -> attempt1 next week Friday',[30],['brain'],st(F,'today',[P('p1','credit_card',500,50,14,'late',2,'2026-10-28')],intent='no'),{'say':{'contains':'Friday 23 October'}})
s('day before holiday: Fri 23 Oct is last bd -> next week last bd Fri 30',[30],['brain'],st(H,'today',[P('p1','credit_card',500,50,14,'late',2,'2026-11-03')],intent='no'),{'say':{'contains':'Friday 30 October'}})
s('refuse attempt1 late -> floor on deadline',[30,'B5'],['brain'],st(W,'prod',[pcc(used=1,offer_date='2026-10-16',offer_amount=500),ppl()],intent='refuse'),{'say':{'contains':'could you pay 50.00 on Friday 23 October'}})
s('refuse attempt2 late -> next product attempt 1',[31,'B4','B5'],['brain'],st(W,'prod',[pcc(used=2,offer_date='2026-10-23',offer_amount=50),ppl()],intent='refuse'),{'idx':1,'say':{'contains':'personal loan: could you pay 300.00 on Friday 16 October'},'P_json':{'contains':'"note": "refused"'}})
s('early band refuse attempt 1 -> refused, notes',[31,'B8'],['brain'],st(W,'prod',[ppl(used=1,offer_date='2026-10-16',offer_amount=300)],intent='no'),{'act':'note','v_note':'refused','v_product_id':'p2'})
s('one date for all after one deadline: capped',['B6','B7',34],['brain'],st(W,'today',[pcc(),ppl()],intent='cant_today',when_words='the 28th',product_ref='all'),
  {'st':'readback','say':{'contains':'your credit card ending 4821: 500.00 on Friday 23 October 2026 (this is the latest date I can record for this product); your personal loan: 300.00 on Wednesday 28 October 2026. Do you confirm?'}})
s('plan label with future date -> promise check not transfer',[29,'B6'],['brain'],st(W,'today',[ppl()],intent='cant_today',when_words='next Friday'),{'st':'readback','say':{'contains':'Friday 23 October'}})
s('next friday said on friday = following week',[22],['brain'],st(F,'today',[P('p2','personal_loan',300,120,3,'early',1,'2026-11-04')],intent='cant_today',when_words='next Friday'),{'say':{'contains':'Friday 23 October'}})
s('weekend date -> offer next business day',[20],['brain'],st(W,'prod',[ppl(used=1,offer_date='2026-10-16',offer_amount=300)],when_words='Saturday'),{'say':{'contains':'Monday 19 October'}})
s('holiday 26 Oct -> offer 27',[20],['brain'],st(W,'prod',[ppl(used=1,offer_date='2026-10-16',offer_amount=300)],when_words='October 26'),{'say':{'contains':'Tuesday 27 October'}})
s('after deadline -> offer deadline',[23,19],['brain'],st(W,'prod',[pcc(used=1,offer_date='2026-10-16',offer_amount=500)],when_words='the 30th'),{'say':{'contains':'latest date I can record is Friday 23 October'}})
s('vague -> ask exact day',[21],['brain'],st(W,'prod',[pcc(used=1,offer_date='2026-10-16',offer_amount=500)],when_words='next week'),{'say':'Which exact day could you pay on?'})
s('vague twice -> propose deadline',[21],['brain'],st(W,'prod',[pcc(used=1,vague=1,offer_date='2026-10-16',offer_amount=500)],when_words='when my salary comes'),{'say':{'contains':'Friday 23 October'}})
s('too much -> floor once',[26,25],['brain'],st(W,'prod',[pcc(used=1,offer_date='2026-10-16',offer_amount=500)],intent='too_much'),{'say':{'contains':'I can record 50.00 for your credit card ending 4821 on Friday 16 October 2026. The rest stays overdue.'}})
s('amount between floor and full accepted',[27],['brain'],st(W,'prod',[pcc(used=1,offer_date='2026-10-16',offer_amount=500)],amount='200',when_words='Friday'),{'st':'readback','say':{'contains':'200.00 on Friday 16 October'}})
s('amount below floor -> offer floor',[27,24],['brain'],st(W,'prod',[pcc(used=1,offer_date='2026-10-16',offer_amount=500)],amount='20'),{'say':{'contains':'cannot record an amount below 50.00'}})
s('loan floor = instalment',[25],['brain'],acct(W,[CL]),{'P_json':{'contains':'"floor": 450.0'}})
s('confirm -> create_promise per product',['B7',34],['brain'],st(W,'readback',[pcc(status='agreed',date='2026-10-16',amount=500),ppl(status='agreed',date='2026-10-20',amount=300)],intent='yes'),{'act':'promise','v_product_id':'p1','v_date':'2026-10-16','v_amount':'500'})
s('promise ok -> next promise',['B7',37],['brain'],st(W,'record',[pcc(status='agreed',date='2026-10-16',amount=500),ppl(status='agreed',date='2026-10-20',amount=300)],pending='promise',r_ok='True',cur_pid='p1'),{'act':'promise','v_product_id':'p2'})
s('promise fail once -> retry',[37],['brain'],st(W,'record',[pcc(status='agreed',date='2026-10-16',amount=500)],pending='promise',r_ok='pending',cur_pid='p1'),{'act':'promise','fails_promise':1})
s('promise fail twice, other recorded -> note service_error',['B11',37],['brain'],st(W,'record',[pcc(status='recorded',date='2026-10-16',amount=500),ppl(status='agreed',date='2026-10-20',amount=300)],pending='promise',r_ok='pending',cur_pid='p2',fails_promise=1),{'act':'note','v_note':'service_error','v_product_id':'p2'})
s('after notes: promise outcome + sms',[38,46,47,'B8'],['brain'],st(W,'notes',[pcc(status='recorded'),ppl(status='service_error',note='service_error',note_done=0)],pending='note',r_ok='True',cur_pid='p2'),{'outcome':'promise','say':{'contains':'You will receive a text message confirming this promise.'}})
s('single product promise fails twice -> no_promise service_error',[37],['brain'],st(W,'notes',[ppl(status='service_error',note='service_error',note_done=1)],pending='note',r_ok='True',cur_pid='p2'),{'outcome':'no_promise','reason':'service_error'})
s('paid one product, continue other',['B9',39],['brain'],st(W,'today',[pcc(),ppl()],intent='paid',product_ref='credit_card'),{'say':{'contains':'Payments can take one business day to appear.'},'idx':1,'P_json':{'contains':'"note": "paid"'}})
s('all paid -> paid',[39,'B8'],['brain'],st(W,'notes',[pcc(status='paid',note='paid',note_done=1),ppl(status='paid',note='paid',note_done=0)],pending='note',r_ok='True',cur_pid='p2'),{'outcome':'paid','reason':''})
s('dispute + refused -> no_promise reason of first non-paid',[40,'B8'],['brain'],st(W,'notes',[pcc(status='paid',note='paid',note_done=1),ppl(status='dispute',note='dispute',note_done=1)],pending='note',r_ok='True',cur_pid='p2'),{'outcome':'no_promise','reason':'dispute'})
s('restructuring transfers, no notes',['B10',41],['brain'],st(W,'prod',[pcc(),ppl()],intent='plan'),{'act':'transfer','v_queue':'restructuring'})
s('transfer ok -> transferred restructuring',['B10',46],['brain'],st(W,'prod',[pcc(status='recorded'),ppl()],pending='transfer',r_ok='True',transfer_key='restructuring'),{'outcome':'transferred','reason':'restructuring'})
s('human first ask',[42],['brain'],st(W,'prod',[pcc()],intent='human'),{'say':{'contains':'can I help you with this myself'}})
s('human second -> general',[42],['brain'],st(W,'prod',[pcc()],intent='human',human_asked=1),{'v_queue':'general','act':'transfer'})
s('hardship -> sympathy + support offer',[32],['brain'],st(W,'today',[pcc()],intent='hardship'),{'st':'support_offer','say':{'contains':'I am sorry to hear that.'}})
s('hardship accept -> support',[32],['brain'],st(W,'support_offer',[pcc()],intent='yes',support_offered=1),{'v_queue':'support'})
s('hardship decline -> note hardship',[32],['brain'],st(W,'support_offer',[pcc()],intent='no',support_offered=1),{'act':'note','v_note':'hardship'})
s('discount refused',[33],['brain'],st(W,'prod',[pcc()],intent='discount'),{'say':{'contains':'cannot offer a discount'}})
s('scam answer',[43],['brain'],st(W,'today',[pcc()],intent='scam'),{'say':{'contains':'customer service number'}})
s('robot answer in confirm',[4,3],['brain'],{'now':W,'title':'Mr','last_name':'Reyes','st':'confirm','intent':'robot'},{'say':{'contains':"Freya Bank's digital assistant. Am I speaking with Mr Reyes?"}})
s('unclear twice -> not_reached unclear',[3],['brain'],{'now':W,'title':'Mr','last_name':'Reyes','st':'confirm','intent':'unclear','confirm_asks':2},{'outcome':'not_reached','reason':'unclear'})
s('refuse talk twice verified -> refused',[45],['brain'],st(W,'prod',[pcc()],intent='refuse_talk',talk_refusals=1),{'act':'note','v_note':'refused'})
s('refuse talk twice before verify -> declined',[45],['brain'],{'now':W,'st':'id_dob','intent':'refuse_talk','talk_refusals':1},{'outcome':'not_verified','reason':'declined'})
s('relative answers -> ask when reachable',[5,10],['brain'],{'now':W,'title':'Ms','last_name':'Reyes','st':'confirm','intent':'not_me'},{'say':'When can Ms Reyes be reached?'})
s('callback tomorrow 11 -> schedule',[6],['brain'],{'now':W,'st':'third','intent':'other','when_words':'tomorrow','time_words':'eleven in the morning'},{'act':'callback','v_cb_date':'2026-10-15','v_cb_time':'11:00'})
s('callback 19:00 included',[6],['brain'],{'now':W,'st':'third','when_words':'today','time_words':'19:00'},{'act':'callback','v_cb_time':'19:00'})
s('callback 19:30 outside -> ask once',[7],['brain'],{'now':W,'st':'third','when_words':'today','time_words':'7:30 pm'},{'cb_out':1,'act':'talk'})
s('callback outside twice -> no_callback',[7],['brain'],{'now':W,'st':'third','when_words':'next Monday','time_words':'11 am','cb_out':1},{'outcome':'not_reached','reason':'no_callback'})
s('callback after window closed today 19:30 now -> next bd friday ok',[6],['brain'],{'now':'2026-10-15T19:30','st':'third','when_words':'tomorrow','time_words':'10 am'},{'act':'callback','v_cb_date':'2026-10-16'})
s('callback Saturday now -> monday',[6],['brain'],{'now':'2026-10-17T12:00','st':'third','when_words':'Monday','time_words':'10:00'},{'act':'callback','v_cb_date':'2026-10-19'})
s('callback ok -> close callback',[6],['brain'],{'now':W,'st':'third','pending':'callback','r_ok':'True'},{'outcome':'not_reached','reason':'callback'})
s('wrong number',[8],['brain'],{'now':W,'st':'confirm','intent':'wrong_number'},{'outcome':'not_reached','reason':'wrong_number'})
s('deceased',[9],['brain'],{'now':W,'st':'third','intent':'deceased'},{'reason':'deceased','say':{'contains':'I am sorry for your loss.'}})
s('dob in pieces -> ask year',[11],['brain'],{'now':W,'st':'id_dob','dob_day':'3','dob_month':'6','dob_year':'none'},{'say':{'contains':'And the year?'}})
s('dob complete -> verify ISO',[11],['brain'],{'now':W,'st':'id_dob','dob_parts':'{"day": 3, "month": 6}','dob_year':'1987'},{'act':'verify','v_answer':'1987-06-03','v_field':'date_of_birth'})
s('bad year ignored',[11],['brain'],{'now':W,'st':'id_dob','dob_day':'3','dob_month':'6','dob_year':'1807'},{'act':'talk'})
s('swapped hint not counted',[13],['brain'],{'now':W,'st':'id_dob','pending':'verify','r_ok':'True','r_hint':'day_month_swapped','r_verified':'False'},{'say':{'contains':'month of your date of birth as a word'},'act':'talk'})
s('dob ok -> phone',[11],['brain'],{'now':W,'st':'id_dob','pending':'verify','r_ok':'True','r_verified':'True','r_all':'False'},{'st':'id_phone'})
s('third wrong -> failed',[12,14],['brain'],{'now':W,'st':'id_phone','pending':'verify','r_ok':'True','r_verified':'False','wrong':2},{'outcome':'not_verified','reason':'failed','say':{'contains':'mobile app or visit a branch'}})
s('all verified -> get_account',[16],['brain'],{'now':W,'st':'id_phone','pending':'verify','r_ok':'True','r_verified':'True','r_all':'True'},{'act':'account'})
s('what about during id -> protect once',[15],['brain'],{'now':W,'st':'id_dob','intent':'what_about','q':'Q?'},{'say':{'contains':'These questions protect your account.'}})
s('id refuse twice -> declined',[15],['brain'],{'now':W,'st':'id_dob','intent':'refuse_id','id_refusals':1},{'reason':'declined'})
s('phone digits merged',[11],['brain'],{'now':W,'st':'id_phone','digits':'21','digits_so_far':'48'},{'v_answer':'4821','act':'verify'})
s('change recorded promise -> app',[36],['brain'],st(W,'readback',[pcc(status='agreed',date='2026-10-16',amount=500)],intent='change_promise'),{'say':{'contains':'mobile app'}})
s('readback change date applied',[35],['brain'],st(W,'readback',[pcc(status='agreed',date='2026-10-16',amount=500)],when_words='Tuesday the 20th',product_ref='credit_card'),{'say':{'contains':'500.00 on Tuesday 20 October'}})
s('question not answerable',[44],['brain'],st(W,'prod',[pcc()],intent='question'),{'say':{'contains':'do not have that information'}})
s('yes today -> all today readback',[28,19],['brain'],st(W,'today',[pcc(),ppl()],intent='yes'),{'say':{'contains':'500.00 on Wednesday 14 October 2026; your personal loan: 300.00 on Wednesday 14 October 2026'}})
s('unreadable dob -> ask again, not counted',[11],['brain'],{'now':W,'st':'id_dob','pending':'verify','r_ok':'False','r_error':'invalid date'},{'act':'talk','say':{'contains':'month as a word'}})
s('robot question with a date: both handled',[4,29],['brain'],st(W,'prod',[ppl(used=1,offer_date='2026-10-16',offer_amount=300)],intent='robot',when_words='Tuesday'),{'say':{'contains':"I am Freya Bank's digital assistant. Let me read back: your personal loan: 300.00 on Tuesday 20 October 2026"}})
json.dump(S,open('out/scenarios.json','w'),indent=1)
