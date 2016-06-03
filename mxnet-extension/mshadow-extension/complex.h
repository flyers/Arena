/*!
 *  Copyright (c) 2016 by Contributors
 * \file complex.h
 * \brief support for complex operations
 * \author Xingjian Shi
 */
#ifndef MSHADOW_EXTENSION_COMPLEX_H_
#define MSHADOW_EXTENSION_COMPLEX_H_
#include <algorithm>
#include "../extension.h"

namespace mshadow {
namespace op {
  namespace complex{
    enum BinaryCalculationType { kBinaryCC, kBinaryCR, kBinaryRC};
    enum UnitaryCalculationType { kUnitaryC2R, kUnitaryC2C };
    struct mul{
      /*! \brief map a_real, a_imag, b_real, b_imag to result using defined operation */
      template<typename DType>
      MSHADOW_XINLINE static DType RealMap(DType a_real, DType a_imag,
        DType b_real, DType b_imag) {
        return a_real * b_real - a_imag * b_imag;
      }
      template<typename DType>
      MSHADOW_XINLINE static DType ImagMap(DType a_real, DType a_imag,
        DType b_real, DType b_imag) {
        return a_real * b_imag + b_real * a_imag;
      }
    };
    struct div{
      /*! \brief map a_real, a_imag, b_real, b_imag to result using defined operation */
      template<typename DType>
      MSHADOW_XINLINE static DType RealMap(DType a_real, DType a_imag,
        DType b_real, DType b_imag) {
        return (a_real * b_real + a_imag * b_imag) / (b_real * b_real + b_imag * b_imag);
      }
      template<typename DType>
      MSHADOW_XINLINE static DType ImagMap(DType a_real, DType a_imag,
        DType b_real, DType b_imag) {
        return (b_real * a_imag - a_real * b_imag) / (b_real * b_real + b_imag * b_imag);
      }
    };
    struct conjugate{
      template<typename TA, typename DType>
      MSHADOW_XINLINE static DType RealMap(const expr::Plan<TA, DType> &src_,
        index_t real_i, index_t real_j, index_t imag_i, index_t imag_j) {
        return src_.Eval(real_i, real_j);
      }
      template<typename TA, typename DType>
      MSHADOW_XINLINE static DType ImagMap(const expr::Plan<TA, DType> &src_,
        index_t real_i, index_t real_j, index_t imag_i, index_t imag_j) {
        return -src_.Eval(imag_i, imag_j);
      }
    };
    struct exchange{
      template<typename TA, typename DType>
      MSHADOW_XINLINE static DType RealMap(const expr::Plan<TA, DType> &src_,
        index_t real_i, index_t real_j, index_t imag_i, index_t imag_j) {
        return src_.Eval(imag_i, imag_j);
      }
      template<typename TA, typename DType>
      MSHADOW_XINLINE static DType ImagMap(const expr::Plan<TA, DType> &src_,
        index_t real_i, index_t real_j, index_t imag_i, index_t imag_j) {
        return src_.Eval(real_i, real_j);
      }
    };
    struct abs_square{
      template<typename TA, typename DType>
      MSHADOW_XINLINE static DType RealMap(const expr::Plan<TA, DType> &src_,
        index_t real_i, index_t real_j, index_t imag_i, index_t imag_j) {
        DType real_val = src_.Eval(real_i, real_j);
        DType image_val = src_.Eval(imag_i, imag_j);
        return real_val * real_val + image_val * image_val;
      }
    };
  }
}

namespace expr {
//--------------------
// ComplexBinaryMapExp
//--------------------
  /*!
* \brief binary map expression lhs [op] rhs where lhs and rhs are complex tensors
* \tparam OP operator
* \tparam calctype type of the calculation
* \tparam TA type of lhs
* \tparam TB type of rhs
* \tparam etype expression type, sa namespace::type
*/
template<int calctype, typename OP, typename TA, typename TB, typename DType, int etype>
struct ComplexBinaryMapExp : public Exp<ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype>,
  DType, etype> {
  /*! \brief left operand */
  const TA &lhs_;
  /*! \brief right operand */
  const TB &rhs_;
  /*! \brief constructor */
  explicit ComplexBinaryMapExp(const TA &lhs, const TB &rhs)
    :lhs_(lhs), rhs_(rhs) {}
};

//-------------------
// ComplexConjExp
//-------------------
/*!
* \brief compute conj(src) where src is a complex tensor
* \tparam TA type of src
* \tparam etype expression type, sa namespace::type
*/
template<int calctype, typename OP, typename TA, typename DType, int etype>
struct ComplexUnitaryExp : public Exp<ComplexUnitaryExp<calctype, OP, TA, DType, etype>,
  DType, etype> {
  /*! \brief source expression */
  const TA &src_;
  /*! \brief constructor */
  explicit ComplexUnitaryExp(const TA &src) : src_(src) {}
};



template<int calctype, typename OP, typename TA, typename TB, typename DType, int ta, int tb>
inline ComplexBinaryMapExp<calctype, OP, TA, TB, DType, (ta | tb | type::kMapper)>
ComplexF(const Exp<TA, DType, ta> &lhs, const Exp<TB, DType, tb> &rhs) {
  return ComplexBinaryMapExp<calctype, OP, TA, TB, DType,
    (ta | tb | type::kMapper)>(lhs.self(), rhs.self());
}

/*!
* \brief conj Negation the imaginary part of A where A is a complex tensor
* \param src source tensor
* \tparam e1 type of source expression
*/
template<int calctype, typename OP, typename SrcExp, typename DType, int e1>
inline ComplexUnitaryExp<calctype, OP, SrcExp, DType, (e1 | type::kMapper)>
ComplexF(const Exp<SrcExp, DType, e1> &src) {
  return ComplexUnitaryExp<calctype, OP, SrcExp, DType, (e1 | type::kMapper)>(src.self());
}

/*!
* \brief conj Negation the imaginary part of A where A is a complex tensor
* \param src source tensor
* \tparam e1 type of source expression
*/
template<typename SrcExp, typename DType, int e1>
inline ComplexUnitaryExp<op::complex::kUnitaryC2C, op::complex::conjugate,
  SrcExp, DType, (e1|type::kMapper)>
conj(const Exp<SrcExp, DType, e1> &src) {
  return ComplexF<op::complex::kUnitaryC2C, op::complex::conjugate>(src);
}

/*!
* \brief complex_exchange Exchange the real and imaginary part of A where A is a complex tensor
* \param src source tensor
* \tparam e1 type of source expression
*/
template<typename SrcExp, typename DType, int e1>
inline ComplexUnitaryExp<op::complex::kUnitaryC2C, op::complex::exchange,
  SrcExp, DType, (e1|type::kMapper)>
complex_exchange(const Exp<SrcExp, DType, e1> &src) {
  return ComplexF<op::complex::kUnitaryC2C, op::complex::exchange>(src);
}

/*!
* \brief complex_abs calculate the modulus of A where A is a complex tensor
* \param src source tensor
* \tparam e1 type of source expression
*/
template<typename SrcExp, typename DType, int e1>
inline ComplexUnitaryExp<op::complex::kUnitaryC2R, op::complex::abs_square,
  SrcExp, DType, (e1 | type::kMapper)>
complex_abs_square(const Exp<SrcExp, DType, e1> &src) {
  return ComplexF<op::complex::kUnitaryC2R, op::complex::abs_square>(src);
}


template<int dim, int calctype, typename OP, typename TA, typename TB,
  typename DType, int etype>
struct ShapeCheck<dim, ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype> > {
  inline static Shape<dim>
    Check(const ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype> &t) {
    Shape<dim> shape1 = ShapeCheck<dim, TA>::Check(t.lhs_);
    Shape<dim> shape2 = ShapeCheck<dim, TB>::Check(t.rhs_);
    if (shape1[0] == 0) return shape2;
    if (shape2[0] == 0) return shape1;
    if (calctype == op::complex::kBinaryCC) {
      CHECK_EQ(shape1, shape2) << "ComplexBinaryMapExp (CC): Shapes of operands are not the same.";
      CHECK_EQ(shape1[dim - 1] % 2, 0) <<
        "ComplexBinaryMapExp (CC): Shape of the last dimension is not even. "
        "We must have real part + imaginary part.";
      return shape1;
    } else if (calctype == op::complex::kBinaryCR) {
      for (int i = 0; i < dim - 1; ++i) {
        CHECK_EQ(shape1.shape_[i], shape2.shape_[i]) <<
          "ComplexBinaryMapExp (CR): Shapes of operands are not the same.";
      }
      CHECK_EQ(shape1[dim - 1], shape2[dim - 1] * 2) <<
        "ComplexBinaryMapExp (CR): Shapes of operands do not match.";
      return shape1;
    } else if (calctype == op::complex::kBinaryRC) {
      for (int i = 0; i < dim - 1; ++i) {
        CHECK_EQ(shape1.shape_[i], shape2.shape_[i]) <<
          "ComplexBinaryMapExp (RC): Shapes of operands are not the same.";
      }
      CHECK_EQ(shape2[dim - 1], shape1[dim - 1] * 2) <<
        "ComplexBinaryMapExp (RC): Shapes of operands do not match.";
      return shape2;
    } else {
      LOG(FATAL) << "ComplexBinaryMapExp: Unexpected Calculation Type!";
      return shape1;
    }
  }
};

template<int dim, int calctype, typename OP, typename TA, typename DType, int etype>
struct ShapeCheck<dim, ComplexUnitaryExp<calctype, OP, TA, DType, etype> > {
  inline static Shape<dim> Check(const ComplexUnitaryExp<calctype, OP, TA, DType, etype> &t) {
    Shape<dim> s = ShapeCheck<dim, TA>::Check(t.src_);
    CHECK_EQ(s[dim - 1] % 2, 0) << "ComplexUnitaryExp: Shape of the last dimension is not even. "
      "We must have real + imaginary.";
    if (calctype == op::complex::kUnitaryC2C) {
      return s;
    } else if (calctype == op::complex::kUnitaryC2R) {
      Shape<dim> s_ret = s;
      s_ret[dim - 1] /= 2;
      return s_ret;
    } else {
      LOG(FATAL) << "ComplexUnitaryExp: Unexpected Calculation Type!";
      return s;
    }
  }
};



// complex binary expression (cc)
template<typename OP, typename TA, typename TB, int etype, typename DType>
class Plan<ComplexBinaryMapExp<op::complex::kBinaryCC, OP, TA, TB, DType, etype>, DType> {
public:
  explicit Plan(const Plan<TA, DType> &lhs, const Plan<TB, DType> &rhs)
    : lhs_(lhs), rhs_(rhs) {}
  MSHADOW_XINLINE DType Eval(index_t y, index_t x) const {
    const index_t base_x = static_cast<index_t>(x / 2) * 2;
    if (x % 2 == 0) {
      return OP::RealMap(lhs_.Eval(y, base_x), lhs_.Eval(y, base_x + 1),
        rhs_.Eval(y, base_x), rhs_.Eval(y, base_x + 1));
    } else{
      return OP::ImagMap(lhs_.Eval(y, base_x), lhs_.Eval(y, base_x + 1),
        rhs_.Eval(y, base_x), rhs_.Eval(y, base_x + 1));
    }
  }

private:
  Plan<TA, DType> lhs_;
  Plan<TB, DType> rhs_;
};

// complex binary expression (cr)
template<typename OP, typename TA, typename TB, int etype, typename DType>
class Plan<ComplexBinaryMapExp<op::complex::kBinaryCR, OP, TA, TB, DType, etype>, DType> {
public:
  explicit Plan(const Plan<TA, DType> &lhs, const Plan<TB, DType> &rhs)
    : lhs_(lhs), rhs_(rhs) {}
  MSHADOW_XINLINE DType Eval(index_t y, index_t x) const {
    const index_t base_x = static_cast<index_t>(x / 2) * 2;
    if (x % 2 == 0) {
      return OP::RealMap(lhs_.Eval(y, base_x), lhs_.Eval(y, base_x + 1),
        rhs_.Eval(y, base_x / 2), static_cast<DType>(0));
    }
    else{
      return OP::ImagMap(lhs_.Eval(y, base_x), lhs_.Eval(y, base_x + 1),
        rhs_.Eval(y, base_x / 2), static_cast<DType>(0));
    }
  }

private:
  Plan<TA, DType> lhs_;
  Plan<TB, DType> rhs_;
};


// complex binary expression (rc)
template<typename OP, typename TA, typename TB, int etype, typename DType>
class Plan<ComplexBinaryMapExp<op::complex::kBinaryRC, OP, TA, TB, DType, etype>, DType> {
public:
  explicit Plan(const Plan<TA, DType> &lhs, const Plan<TB, DType> &rhs)
    : lhs_(lhs), rhs_(rhs) {}
  MSHADOW_XINLINE DType Eval(index_t y, index_t x) const {
    const index_t base_x = static_cast<index_t>(x / 2) * 2;
    if (x % 2 == 0) {
      return OP::RealMap(lhs_.Eval(y, base_x / 2), static_cast<DType>(0),
        rhs_.Eval(y, base_x), rhs_.Eval(y, base_x + 1));
    }
    else{
      return OP::ImagMap(lhs_.Eval(y, base_x / 2), static_cast<DType>(0),
        rhs_.Eval(y, base_x), rhs_.Eval(y, base_x + 1));
    }
  }

private:
  Plan<TA, DType> lhs_;
  Plan<TB, DType> rhs_;
};


// complex unitary expression (c2c)
template<typename OP, typename TA, int etype, typename DType>
class Plan<ComplexUnitaryExp<op::complex::kUnitaryC2C, OP, TA, DType, etype>, DType> {
public:
  explicit Plan(const Plan<TA, DType> &src) : src_(src) {}
  MSHADOW_XINLINE DType Eval(index_t y, index_t x) const {
    const index_t base_x = static_cast<index_t>(x / 2) * 2;
    if (0 == x % 2) {
      return OP::RealMap(src_, y, base_x, y, base_x + 1);
    }
    else {
      return OP::ImagMap(src_, y, base_x, y, base_x + 1);
    }
  }

private:
  Plan<TA, DType> src_;
};

// complex unitary expression (c2r)
template<typename OP, typename TA, int etype, typename DType>
class Plan<ComplexUnitaryExp<op::complex::kUnitaryC2R, OP, TA, DType, etype>, DType> {
public:
  explicit Plan(const Plan<TA, DType> &src) : src_(src) {}
  MSHADOW_XINLINE DType Eval(index_t y, index_t x) const {
    return OP::RealMap(src_, y, x * 2, y, x * 2 + 1);
  }

private:
  Plan<TA, DType> src_;
};



template<int calctype, typename OP, typename TA, typename TB, typename DType, int etype>
inline Plan<ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype>, DType>
MakePlan(const ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype> &e) {
  return Plan<ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype>,
    DType>(MakePlan(e.lhs_), MakePlan(e.rhs_));
}

template<int calctype, typename OP, typename TA, typename DType, int etype>
inline Plan<ComplexUnitaryExp<calctype, OP, TA, DType, etype>, DType>
MakePlan(const ComplexUnitaryExp<calctype, OP, TA, DType, etype> &e) {
  return Plan<ComplexUnitaryExp<calctype, OP, TA, DType, etype>,
    DType>(MakePlan(e.src_));
}



template<int calctype, typename OP, typename TA, typename TB, typename DType, int etype>
struct ExpInfo<ComplexBinaryMapExp<calctype, OP, TA, TB, DType, etype> > {
  static const int kDimLhs = ExpInfo<TA>::kDim;
  static const int kDimRhs = ExpInfo<TB>::kDim;
  static const int kDim = (kDimLhs >= 0 && kDimRhs >= 0) ? \
    (kDimLhs == 0 ? \
  kDimRhs : \
            ((kDimRhs == 0 || kDimLhs == kDimRhs) ? kDimLhs : -1)) : -1;
  static const int kDevMask = ExpInfo<TA>::kDevMask & ExpInfo<TB>::kDevMask;
};

template<int calctype, typename OP, typename TA, typename DType, int etype>
struct ExpInfo<ComplexUnitaryExp<calctype, OP, TA, DType, etype> > {
  static const int kDim = ExpInfo<TA>::kDim;
  static const int kDevMask = ExpInfo<TA>::kDevMask;
};

}  // namespace expr
}  // namespace mshadow
#endif  // MSHADOW_EXTENSION_COMPLEX_H_
