import numpy as np
from collections import OrderedDict
from itertools import groupby



# 之所以要添加wzq2这个文件是因为这边的估值函数有所改变
# 因为估值函数几乎是这个文件本身的根基，所以，为了慎重考虑就这样了
# 另外一个重要的改变就是深度树的搜索会仅仅只考虑杀棋链来进行
# 可能是因为之前的估值函数一下子就做到了简单难度偏上这样的程度于是就似乎有点失去方向的感觉


# 五子棋类
# 包装了下棋函数，判断是否胜利函数以及估值函数，深度搜索估值函数。
# 下棋函数如果返回值为真则在该点下棋，否则下棋失败（被其他棋子占用）
# 每下一步棋就会更新 self.win 。如果该值不为 False 则为胜利者
# player in[1, 2]
class WZQ:
    def __init__(self, h, w):
        self.s_map = np.zeros((h,w)).astype(np.int32)


        self.h = h
        self.w = w
        self._lu = np.zeros((h,w)).astype(np.bool8)
        self._ru = np.zeros((h,w)).astype(np.bool8)
        self._area_eval = np.zeros((h,w),dtype=np.int32)
        self._scal_eval = self._create_scal(5)
        self._scal_ecal_large = self._create_scal(9)
        self.win = False

        #分值列表，如果有新加入的估值，按照分值顺序插入即可。
        self._values = OrderedDict([
            [(1,1,1,1,1),1000],#活五1000分
            [(1,0,1,1,1,0,1),400],#活四
            [(0,1,1,1,1,0),400],#活四
            [(1,1,1,1,0),100],#冲四
            [(1,1,1,0,1),100],#冲四
            [(1,1,0,1,1),100],#冲四
            [(1,0,1,1,1),100],#冲四
            [(0,1,1,1,1),100],#冲四
            [(0,1,1,1,0,0),100],#活三
            [(0,0,1,1,1,0),100],#活三
            #优冲三：因为这里如果被对手中间截断也能很快再生成冲三，所以分值较高
            [(0,0,0,1,1,0,1),50],#优冲三
            [(1,0,1,1,0,0,0),50],#优冲三
            [(0,0,1,0,1,0,1),30],#优眠三
            [(1,0,1,0,1,0,0),30],#优眠三
            #劣冲三：因为这里如果被对手截断那么在这一维就直接失去价值所以分值低
            [(1,1,1,0,0),20],#劣冲三
            [(0,0,1,1,1),20],#劣冲三
            [(1,1,0,1,0),20],#劣冲三
            [(0,1,0,1,1),20],#劣冲三
            [(0,1,1,0,0),6],#活二
            [(0,0,1,1,0),6],#活二
            [(0,1,0,1,0),6],#活二
            [(1,0,1,0,0),2],#冲二
            [(0,0,1,0,1),2],#冲二
            [(1,1,0,0,0),2],#冲二
            [(0,0,0,1,1),2],#冲二
            [(0,0,0,0,1),1],#一
            [(0,0,0,1,0),1],#一
            [(0,0,1,0,0),1],#一
            [(0,1,0,0,0),1],#一
            [(1,0,0,0,0),1],#一
            ])






    ##ls = []
    ##def some(深度, 权重图, ls, chain=[]):
    ##    新的权重图 = 添权重函数(权重图, chain)
    ##    ## 这里的400主要是因为这是最接近活五的分值
    ##    if 新的权重图.max() >= 400 or 深度==目标深度:
    ##        对 ls 添加 chain 的信息
    ##        return
    ##    for point in 新的范围图.所有点:
    ##        some(深度, 权重图, ls, chain+[point])


    #临时权重图
    def eval_map_add(self, eval_map, player, chain):
        eval_map = eval_map.copy()
        if chain:
            ph,pw = point = chain[-1]
            (u,l) = np.maximum(np.array(point)-4, 0)
            (d,r) = np.minimum(np.array(point)+5, self.s_map.shape)
            gu,gl,gd,gr = 4-(ph-u), 4-(pw-l), 4+(d-ph), 4+(r-pw)
            z = np.zeros((self.h,self.w),dtype=np.int32)
            z[u:d,l:r] |= self._scal_ecal_large[gu:gd,gl:gr]
            for point in  np.vstack(np.where((z==1)&(self.s_map==0))).transpose():
                eval_map[tuple(point)] = self.evaluate(tuple(point), player)# + self.evaluate(tuple(point), 3-player)*.5
        return eval_map

    #棋谱的栈形式的调用push pop, 仅仅使用原有落子图，对计算空间的优化
    def _s_map_push(self, player_chain, chain):
        if chain:
            player = player_chain[len(chain)]
            self.s_map[tuple(chain[-1])] = player

    def _s_map_pop(self, player_chain, chain):
        if chain:
            player = player_chain[len(chain)]
            self.s_map[tuple(chain[-1])] = 0



    def _get_evaluation_points(self, eval_map1, eval_map2, limit):
        v = np.stack((eval_map1, eval_map2),-1)
        _max_value = np.max(v,-1)
        _max_index = np.argmax(v,-1)
        _points_map = (np.max(v,-1)>=100) & (self.s_map==0) # 每次只考虑双方大于活三的所有点, 如果没有则链断
        if not np.any(_points_map):
            return []
        _eval = _max_value[_points_map][np.argsort(_max_value[_points_map])][::-1]# 这个就是该点下双方中最大的估值
        _indx = np.stack(np.where(_points_map),-1)[np.argsort(_max_value[_points_map])][::-1]# 这个就是该点下双方中最大的估值坐标

        # 只取我方胜点
        toggle = True
        x = []
        for key_value in sorted(set(_eval))[::-1]:
            p = []
            if toggle:
                for point,value in zip(_indx,_eval):
                     if value == key_value and value >= limit:
                        print(_max_index[tuple(point)])
                        if _max_index[tuple(point)] == 0:
                            p += [point]
                        else:
                            toggle = False
            x += p
            print(x)
            print(_eval)
            print(_indx)
            raise
            
        return x

        
    # 这里主要是修改成只考虑杀棋链, 在这样的考虑下, 估值函数就只考虑自己权值就好了.
    # 因为估值当前的估值函数只会和下一层的对方估值函数进行比对, 这样就能更加精确的控制调整范围.
    # 一般的杀棋链都比较少, 因此, 这样的深度搜索也能直接不考虑其他直接深度搜到自己胜利为止.
    # 策略修改后, 奇数层只考虑自己, 偶数层只考虑对面
    # 如果在奇数层的某一点的下一层有比该点分值高的点, 那么奇数层的该点就不用考虑了.
    # 如果在偶数层的某一点的下一层有比该点分值高的点, 那么下一层就只考虑这些分值高的点.
    def pred(self, target_deep, player):
        ls = []
        # 下棋顺序 player_chain 暂以下述方式存放，index==0位不用管
        if player==1: player_chain = [-1]+[1,2]*20
        if player==2: player_chain = [-1]+[2,1]*20

        alpha=float('-inf')
        beta =float('-inf')

        eval_map1 = self._calc_eval_map(player)
        eval_map2 = self._calc_eval_map(3-player)

        def funcition(deep, eval_map1, eval_map2, ls, alpha, beta, chain=[], value_chain=[]):
            self._s_map_push(player_chain, chain)
            eval_map1  = self.eval_map_add(eval_map1, player, chain)#权重图1
            eval_map2  = self.eval_map_add(eval_map2, 3-player, chain)#权重图2
            
            pred_player = player if not len(chain)%2 else 3-player
            if pred_player == player  : eval_map = eval_map1
            if pred_player == 3-player: eval_map = eval_map2
            
            if chain and (self._jug_win(chain[-1]) or deep == target_deep):
                ls+=[(chain,(value_chain))]
                self._s_map_pop(player_chain, chain)
                if self._jug_win(chain[-1]):
                    return 1000
                else:
                    return 999

            if pred_player == player  : x = self._get_evaluation_points(eval_map1, eval_map2, 100)
            if pred_player == 3-player: x = self._get_evaluation_points(eval_map2, eval_map1, 400)

            print(*chain,'next lv node num:',len(x))
            for point in x:
                v = funcition(deep+1, eval_map1, eval_map2, ls, alpha, beta, chain+[(point)], value_chain+[np.maximum(eval_map1, eval_map2)[tuple(point)]])
                if v == 1000:
                    break

            self._s_map_pop(player_chain, chain)
            return eval_map.max()

        funcition(1, eval_map1, eval_map2, ls, alpha, beta)
        return ls
    # 转念一想, 这样的策略会比之前的考虑要通用很多
    # 明天再继续 debug















    

    #米字形的矩阵生成，用于优化计算范围
    def _create_scal(self, n):
        c = int(n/2)
        v = np.zeros((n,n),dtype=np.int32)
        v[c,:],v[:,c] = 1,1
        v = np.eye(n,dtype=np.int32)|np.eye(n,dtype=np.int32)[:,::-1]|v
        return v
    
    #找到一个点所在位置的横竖斜上的所有点以及该点在其array里的坐标
    def _find_crossNslash(self, point):
        oh,ow = self.s_map.shape
        h,w = point
        self._lu = np.eye(oh,ow,w-h).astype(np.bool8)
        self._ru = np.eye(oh,ow,ow-w-1-h).astype(np.bool8)[:,::-1]
        ph,harray = w,self.s_map[h,:]
        pw,warray = h,self.s_map[:,w]    
        plu,luarray = min((h,w))        ,self.s_map[self._lu]
        pru,ruarray = min((h,ow-w-1))   ,self.s_map[self._ru]
        return [(ph,harray),(pw,warray),(plu,luarray),(pru,ruarray)]
    
    #判断胜利
    def _jug_win(self, point):
        for idx,arr in self._find_crossNslash(point):
            for i,j in groupby(arr):
                if i!=0 and len(list(j)) >= 5:
                    return i
        return False
    
    #确保当前point没有其他落子
    #确保每下一步都会更新 self.win 。
    def play_1_round(self, point, player):
        assert player in [1,2]
        if self.s_map[point] != 0:
            return False
        self.s_map[point] = player
        self._area_eval_add(point)
        self.win = self._jug_win(point)
        return True

    #根据自身修正 array 排除对手棋子的干扰
    def _revise_array(self, idx, arr, player):
        k = 3 - player
        v = np.where(arr[:idx]==k)[0]
        minx = v.max() + 1 if len(v) else 0
        ridx = idx - minx if len(v) else idx
        v = np.where(arr[idx:]==k)[0]
        maxx = v.min() + idx if len(v) else len(arr)
        return ridx,arr[minx:maxx]

    #估值算法
    def evaluate(self, point, player):
        assert self.s_map[point] == 0 #函数只估值未下过棋的点
        self.s_map[point] = player
        core = 0
        for idx,arr in self._find_crossNslash(point):
            idx,arr = self._revise_array(idx, arr, player)
            _core_list = []
            for val in self._values:
                iidx = idx - len(val)+1 if idx - len(val)+1 > 0 else 0
                jidx = idx + 1
                _val = np.array(val) * player
                for i in range(iidx,jidx):
                    _arr = arr[i:i+len(_val)]
                    if len(_arr) == len(_val) and np.any(_arr^_val)==False:
                        _core_list.append(self._values[val])
                        break
                if len(_core_list)!= 0:
                    break
            core = max(core, max(_core_list) if len(_core_list) else 0)
        #估值结束再把 s_map 原本样子还回去
        self.s_map[point] = 0
        return core

    #需要计算估值的范围
    def _area_eval_add(self, point):
        ph,pw = point
        (u,l) = np.maximum(np.array(point)-2, 0)
        (d,r) = np.minimum(np.array(point)+3, self.s_map.shape)
        gu,gl,gd,gr = 2-(ph-u), 2-(pw-l), 2+(d-ph), 2+(r-pw)
        self._area_eval[u:d,l:r] |= self._scal_eval[gu:gd,gl:gr]

    #将估值函数包装一下，使得使用起来会更加方便
    def _calc_eval_map(self, player):
        self._temp1_eval_map = np.zeros(self.s_map.shape).astype(np.int32)
        self._temp2_eval_map = np.zeros(self.s_map.shape).astype(np.int32)
        for i,j in np.vstack(np.where((self._area_eval==1)&(self.s_map==0))).transpose():
            self._temp1_eval_map[i,j] = self.evaluate((i,j),player)
        for i,j in np.vstack(np.where((self._area_eval==1)&(self.s_map==0))).transpose():
            self._temp2_eval_map[i,j] = self.evaluate((i,j),3-player)
        #这里的0.8是为了防止在预测中对手权重过高过度防御导致连自己的连五都被无视
        return (self._temp1_eval_map+self._temp2_eval_map*.8)

    #test 一层的逻辑
    #经过测试，该简单算法不能应对较为复杂的多层考虑，仅仅应用于简单难度，对新手来说该算法胜率还不错
    def robot_level1(self, player):
        v = self._calc_eval_map(player)
        v = np.vstack(np.where(v==v.max())).transpose()
        v = v[np.random.choice(range(len(v)))]
        return v


    #尝试用高斯函数的缓斜坡坡对 value_chain 进行加权平均
    def _calc_value_by_gaussian(self,preds,xita):
        goss = lambda x,xita:1/((2*np.pi*xita)**.5)*np.exp(-(x-0)**2/(2*xita**2))
        f_chain,f_ls,f_value = None,None,0
        for chain,ls in preds:
            ls_value = sum([goss(idx,xita)*i for idx,i in enumerate(ls)])/len(ls)
            print(chain,ls,ls_value)
            if ls_value > f_value:
                f_chain,f_ls,f_value = chain,ls,ls_value
        return f_chain,f_ls,f_value

    #直接用平均值来处理
    def _calc_value_by_mean(self,preds,xita):
        f_chain,f_ls,f_value = None,None,0
        for chain,ls in preds:
            ls_value = np.mean(ls)
            print(chain,ls,ls_value)
            if ls_value > f_value:
                f_chain,f_ls,f_value = chain,ls,ls_value
        return f_chain,f_ls,f_value

    # 直接用最后值大小来处理
    def _calc_value_by_lastone(self,preds,xita):
        f_chain,f_ls,f_value = None,None,0
        for chain,ls in preds:
            ls_value = ls[-1]
            print(chain,ls,ls_value)
            if ls_value > f_value:
                f_chain,f_ls,f_value = chain,ls,ls_value
        return f_chain,f_ls,f_value

    #因考虑落子次序可能对下棋会有一定影响    
    def robot_level3(self, player):
        target_deep = 6
        preds = self.pred(target_deep, player)
        f_chain,f_ls,f_value = self._calc_value_by_lastone(preds,7)
        print(*f_chain,end=' ')
        print(np.around(f_ls),f_value)
        return f_chain[0]
    








#以下只用于简单语法错误的检查测试test
if __name__== '__main__':
    wzq = WZQ(15,15)
    player = 2
##    print(wzq.play_1_round((0,6),1))
##    print(wzq.play_1_round((1,4),1))
##    print(wzq.play_1_round((3,2),1))
##    print(wzq.play_1_round((3,7),1))
##    print(wzq.play_1_round((6,4),1))
##    print(wzq.play_1_round((1,5),player))
##    print(wzq.play_1_round((2,4),player))
##    print(wzq.play_1_round((3,3),player))
##    print(wzq.play_1_round((3,5),player))
####    print(wzq.play_1_round((4,2),player))
##    print(wzq.play_1_round((4,4),player))
##    print(wzq.play_1_round((3,4),player))
    
    print(wzq.play_1_round((12,12),1))
    print(wzq.play_1_round((13,13),1))
    print(wzq.play_1_round((14,14),1))
    print(wzq.play_1_round((7,12),1))
    print(wzq.play_1_round((7,13),1))
    print(wzq.play_1_round((7,14),1))
    print(wzq.play_1_round((8,12),1))
    print(wzq.play_1_round((8,13),1))
    print(wzq.play_1_round((8,14),1))
##    print(wzq.play_1_round((6,12),2))
##    print(wzq.play_1_round((6,13),2))
##    print(wzq.play_1_round((6,14),2))
##    print(wzq.play_1_round((9,12),2))
##    print(wzq.play_1_round((9,13),2))
##    print(wzq.play_1_round((9,14),2))
    print(wzq.play_1_round((11,9),2))

    print(wzq.s_map)
    import time

    _t = time.time()
    print(wzq.evaluate((2,2),2))
    h,w = wzq.s_map.shape
    v = np.zeros(wzq.s_map.shape).astype(np.int32)
    for i,j in np.vstack(np.where(wzq._area_eval==1)).transpose():
        if wzq.s_map[i,j] == 0:
            v[i,j] = wzq.evaluate((i,j),1)
    print(v)
    print(time.time()-_t)

    
    _t = time.time()
    print(wzq._calc_eval_map(2).astype(np.int32))   
    print(time.time()-_t)
    _t = time.time()
##    v = wzq.pred(3, 1)
    v = wzq.robot_level1(1)
    print('fin1:',v)
    v = wzq.robot_level3(1)
    print('fin2:',v)
    print(time.time()-_t)

    print(wzq.s_map)
